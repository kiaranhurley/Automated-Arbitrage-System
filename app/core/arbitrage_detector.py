import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.models import (ArbitrageOpportunity, ExchangeRate, PricePoint,
                               Product)
from app.utils.currency_converter import CurrencyConverter
from app.utils.fee_calculator import FeeCalculator
from config import ARBITRAGE_CONFIG

# Import free-to-play games list
# try:
#     from fix_steam_scraper import FREE_TO_PLAY_GAMES
# except ImportError:
#     # Fallback list if fix_steam_scraper.py is not available
#     FREE_TO_PLAY_GAMES = [
#         "730",    # Counter-Strike 2
#         "570",    # Dota 2
#         "1172470", # Apex Legends
#         "578080", # PUBG: BATTLEGROUNDS 
#         "1085660", # Destiny 2
#         "440",    # Team Fortress 2
#         "252490", # Rust
#         "304930", # Unturned
#         "230410", # Warframe
#         "218620", # PAYDAY 2
#         "221100", # DayZ
#         "359550", # Rainbow Six Siege
#     ]

# Cache of detected free-to-play games (product_id -> bool)
FREE_TO_PLAY_CACHE = {}

class ArbitrageDetector:
    def __init__(self, db_session: Session):
        self.session = db_session
        self.logger = logging.getLogger("arbitrage_detector")
        self.min_profit_margin = ARBITRAGE_CONFIG['min_profit_margin']
        self.min_absolute_profit = ARBITRAGE_CONFIG['min_absolute_profit']
        self.max_investment = ARBITRAGE_CONFIG['max_investment']
        self.max_hold_time = ARBITRAGE_CONFIG['max_hold_time']
        
        # Initialize utilities
        self.currency_converter = CurrencyConverter(db_session)
        self.fee_calculator = FeeCalculator(db_session)

    def find_opportunities(self):
        """Find arbitrage opportunities across all marketplaces"""
        try:
            # Get current price points within the last hour
            current_time = datetime.utcnow()
            
            recent_prices = self.session.query(PricePoint).filter(
                PricePoint.timestamp >= current_time - timedelta(hours=1)
            ).options(
                joinedload(PricePoint.product),
                joinedload(PricePoint.marketplace)
            ).all()

            opportunities = []
            processed_pairs = set()
            
            # Track free-to-play games already checked to avoid repeated logging
            checked_free_games = set()

            for source_price in recent_prices:
                # Skip if this is a free-to-play game on any platform
                product_id = source_price.product_id
                
                if product_id in checked_free_games:
                    continue
                    
                if self._is_free_to_play(product_id):
                    checked_free_games.add(product_id)
                    # Log once at debug level for each product ID
                    self.logger.debug(f"Skipping free-to-play game (Product ID: {product_id})")
                    continue
                    
                # Convert price to base currency if needed
                converted_buy_price = source_price.price
                if source_price.currency != 'EUR':
                    converted_buy_price = self.currency_converter.convert(
                        source_price.price,
                        source_price.currency
                    )
                    
                if converted_buy_price is None or converted_buy_price > self.max_investment:
                    continue

                # Find matching products with lower prices
                target_prices = self.session.query(PricePoint).options(
                    joinedload(PricePoint.product),
                    joinedload(PricePoint.marketplace)
                ).filter(
                    and_(
                        PricePoint.product_id == source_price.product_id,
                        PricePoint.marketplace_id != source_price.marketplace_id,
                        PricePoint.timestamp >= current_time - timedelta(hours=1)
                    )
                ).all()

                for target_price in target_prices:
                    # Convert target price to base currency if needed
                    converted_sell_price = target_price.price
                    if target_price.currency != 'EUR':
                        converted_sell_price = self.currency_converter.convert(
                            target_price.price,
                            target_price.currency
                        )
                    
                    if converted_sell_price is None or converted_sell_price <= converted_buy_price:
                        continue

                    # Skip if we've already processed this pair
                    pair_key = (min(source_price.id, target_price.id),
                              max(source_price.id, target_price.id))
                    if pair_key in processed_pairs:
                        continue

                    opportunity = self._analyze_opportunity(
                        source_price,
                        target_price,
                        converted_buy_price,
                        converted_sell_price
                    )
                    
                    if opportunity:
                        opportunities.append(opportunity)
                        processed_pairs.add(pair_key)

            return opportunities

        except Exception as e:
            self.logger.error(f"Error finding arbitrage opportunities: {str(e)}")
            return []

    def _is_free_to_play(self, product_id):
        """
        Check if a game is free-to-play based on its price data.
        Uses a cache to avoid repeated database queries.
        """
        try:
            # First check cache to avoid repeated checks
            if product_id in FREE_TO_PLAY_CACHE:
                return FREE_TO_PLAY_CACHE[product_id]
                
            # Get the product to get its name for logging
            product = self.session.query(Product).filter_by(id=product_id).first()
            if not product:
                return False
            
            # Get the most recent price points for this product across all marketplaces
            current_time = datetime.utcnow()
            recent_prices = self.session.query(PricePoint).filter(
                and_(
                    PricePoint.product_id == product_id,
                    PricePoint.timestamp >= current_time - timedelta(hours=24)
                )
            ).all()
            
            # If there are no price records, we can't determine if it's free
            if not recent_prices:
                return False
                
            # If any major marketplace has a price of 0 or very close to 0, consider it free-to-play
            for price in recent_prices:
                # Skip price points without marketplace info
                if not price.marketplace:
                    continue
                    
                marketplace_name = price.marketplace.name.lower()
                
                # Check if this is a major platform with a zero price
                if marketplace_name in ['steam', 'epic games', 'origin'] and price.price < 1.0:
                    # This is a free or very cheap game
                    self.logger.info(f"Detected free/cheap game: '{product.name}' on {marketplace_name} (price: {price.price})")
                    FREE_TO_PLAY_CACHE[product_id] = True
                    return True
            
            # No marketplace has it for free
            FREE_TO_PLAY_CACHE[product_id] = False
            return False
                
        except Exception as e:
            self.logger.error(f"Error checking if game is free-to-play: {str(e)}")
            return False  # Default to not free-to-play in case of error

    def _analyze_opportunity(self, source_price, target_price, converted_buy_price, converted_sell_price):
        """Analyze potential arbitrage opportunity between two price points"""
        try:
            # Validate input
            if not source_price or not target_price:
                self.logger.warning("Cannot analyze opportunity with missing price data")
                return None
                
            # Skip if either price is -1 (N/A placeholder)
            if source_price.price == -1 or target_price.price == -1:
                self.logger.debug(f"Skipping opportunity involving N/A price for {source_price.product.name if source_price.product else 'unknown product'}")
                return None
                
            # Ensure both prices have required attributes
            if not hasattr(source_price, 'marketplace_id') or not hasattr(target_price, 'marketplace_id'):
                self.logger.warning("Price points missing marketplace_id attribute")
                return None
                
            # Calculate profit metrics including fees
            profit_data = self.fee_calculator.calculate_net_profit(
                converted_buy_price,
                converted_sell_price,
                source_price.marketplace_id,
                target_price.marketplace_id
            )

            # Calculate profit margin based on net profit
            profit_margin = (profit_data['net_profit'] / converted_buy_price) * 100

            # Check if opportunity meets minimum requirements
            if profit_margin < self.min_profit_margin or profit_data['net_profit'] < self.min_absolute_profit:
                return None

            # Calculate risk score
            risk_score = self._calculate_risk_score(source_price, target_price)

            # Create opportunity object
            opportunity = ArbitrageOpportunity(
                source_price_id=source_price.id,
                target_price_id=target_price.id,
                profit_margin=profit_margin,
                absolute_profit=profit_data['net_profit'],
                risk_score=risk_score,
                detected_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=self.max_hold_time)
            )

            # Store fee breakdown in metadata
            opportunity.metadata = {
                'fee_breakdown': profit_data['fee_breakdown'],
                'gross_profit': profit_data['gross_profit'],
                'total_fees': profit_data['total_fees']
            }

            return opportunity

        except Exception as e:
            self.logger.error(f"Error analyzing opportunity: {str(e)}")
            return None

    def _calculate_risk_score(self, source_price, target_price):
        """Calculate risk score for an arbitrage opportunity"""
        try:
            risk_factors = {
                'price_volatility': self._calculate_price_volatility(source_price.product_id),
                'marketplace_reliability': self._get_marketplace_reliability(source_price.marketplace_id),
                'time_sensitivity': self._calculate_time_sensitivity(source_price, target_price),
                'currency_risk': self._calculate_currency_risk(source_price.currency, target_price.currency)
            }

            # Weight the risk factors
            weights = {
                'price_volatility': 0.3,
                'marketplace_reliability': 0.3,
                'time_sensitivity': 0.2,
                'currency_risk': 0.2
            }

            risk_score = sum(score * weights[factor] for factor, score in risk_factors.items())
            return min(max(risk_score, 0), 1)  # Ensure score is between 0 and 1

        except Exception as e:
            self.logger.error(f"Error calculating risk score: {str(e)}")
            return 0.5  # Return medium risk on error

    def _calculate_price_volatility(self, product_id):
        """Calculate price volatility for a product"""
        try:
            # Get price history for the last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            price_history = self.session.query(PricePoint).filter(
                and_(
                    PricePoint.product_id == product_id,
                    PricePoint.timestamp >= thirty_days_ago
                )
            ).all()

            if not price_history:
                return 0.5

            # Calculate standard deviation of prices
            prices = [p.converted_price for p in price_history]
            from numpy import mean, std
            price_std = std(prices)
            price_mean = mean(prices)

            # Normalize volatility score
            volatility = price_std / price_mean if price_mean > 0 else 0
            return min(volatility, 1)

        except Exception as e:
            self.logger.error(f"Error calculating price volatility: {str(e)}")
            return 0.5

    def _get_marketplace_reliability(self, marketplace_id):
        """Get reliability score for a marketplace"""
        # This could be based on historical successful transactions
        # For now, return a default value
        return 0.8

    def _calculate_time_sensitivity(self, source_price, target_price):
        """Calculate time sensitivity of the opportunity"""
        try:
            # Check if either price is part of a sale
            is_sale = False
            
            # Safely check source metadata
            if hasattr(source_price, 'metadata'):
                source_metadata = source_price.metadata
                if isinstance(source_metadata, dict):
                    is_sale = is_sale or source_metadata.get('is_sale', False)
                elif source_metadata is not None:
                    # If metadata exists but isn't a dict, try checking is_sale attribute
                    is_sale = is_sale or getattr(source_metadata, 'is_sale', False)
            
            # Safely check target metadata
            if hasattr(target_price, 'metadata'):
                target_metadata = target_price.metadata
                if isinstance(target_metadata, dict):
                    is_sale = is_sale or target_metadata.get('is_sale', False)
                elif target_metadata is not None:
                    # If metadata exists but isn't a dict, try checking is_sale attribute
                    is_sale = is_sale or getattr(target_metadata, 'is_sale', False)

            if is_sale:
                return 0.7  # Higher risk for sale items

            return 0.3  # Lower risk for regular prices

        except Exception as e:
            self.logger.error(f"Error calculating time sensitivity: {str(e)}")
            return 0.5

    def _calculate_currency_risk(self, source_currency, target_currency):
        """Calculate currency exchange risk"""
        try:
            if source_currency == target_currency:
                return 0.1  # Low risk for same currency

            # Get currency volatility from exchange rate history
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            exchange_rates = self.session.query(ExchangeRate).filter(
                and_(
                    ExchangeRate.from_currency == source_currency,
                    ExchangeRate.to_currency == target_currency,
                    ExchangeRate.timestamp >= thirty_days_ago
                )
            ).all()

            if not exchange_rates:
                return 0.5

            rates = [rate.rate for rate in exchange_rates]
            from numpy import mean, std
            rate_std = std(rates)
            rate_mean = mean(rates)

            # Normalize volatility score
            volatility = rate_std / rate_mean if rate_mean > 0 else 0
            return min(volatility, 1)

        except Exception as e:
            self.logger.error(f"Error calculating currency risk: {str(e)}")
            return 0.5

    def cleanup_free_to_play_opportunities(self):
        """
        Clean up any existing arbitrage opportunities involving free-to-play games.
        Uses price data to dynamically detect free games.
        """
        try:
            count = 0
            
            # Find all active opportunities
            opportunities = self.session.query(ArbitrageOpportunity).filter_by(status='active').all()
            
            for opp in opportunities:
                # Get product ID from the source price
                product_id = opp.source_price.product_id
                
                # Check if this is a free-to-play game
                if self._is_free_to_play(product_id):
                    # Set status to expired
                    opp.status = 'expired'
                    product_name = opp.source_price.product.name if opp.source_price.product else f"Product ID {product_id}"
                    self.logger.info(f"Marking opportunity {opp.id} as expired because '{product_name}' is free-to-play")
                    count += 1
            
            # Commit changes if any opportunities were marked as expired
            if count > 0:
                self.session.commit()
                
            return count

        except Exception as e:
            self.logger.error(f"Error cleaning up free-to-play opportunities: {str(e)}")
            self.session.rollback()
            return 0 