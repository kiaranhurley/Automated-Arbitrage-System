import asyncio
import logging
import urllib.parse
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from sqlalchemy import create_engine, func
from sqlalchemy.orm import joinedload, sessionmaker

from app.core.arbitrage_detector import FREE_TO_PLAY_CACHE, ArbitrageDetector
from app.marketplace.steam_scraper import SteamScraper
from app.models.models import (ArbitrageOpportunity, Marketplace, PricePoint,
                               Product, init_db)
from app.notifications.notification_system import NotificationSystem
from config import DATABASE_CONFIG, FLASK_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.config.update(FLASK_CONFIG)
socketio = SocketIO(app)

# Database setup
password = urllib.parse.quote_plus(DATABASE_CONFIG['default']['PASSWORD'])
db_url = f"postgresql://{DATABASE_CONFIG['default']['USER']}:{password}@{DATABASE_CONFIG['default']['HOST']}:{DATABASE_CONFIG['default']['PORT']}/{DATABASE_CONFIG['default']['NAME']}"
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

# Initialize components
def init_components():
    """Initialize system components and database"""
    try:
        global engine, Session
        
        # Initialize database
        engine = init_db()
        Session = sessionmaker(bind=engine)
        
        # Initialize marketplace records if they don't exist
        session = Session()
        try:
            if session.query(Marketplace).count() == 0:
                steam = Marketplace(
                    name="Steam",
                    base_url="https://store.steampowered.com",
                    api_enabled=True,
                    scraping_enabled=True,
                    active=True
                )
                session.add(steam)
                session.commit()
        finally:
            session.close()
        
        # Clean up any incorrect entries for free-to-play games
        cleanup_free_to_play_games()
        
        logger.info("System components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize components: {str(e)}")
        raise

def cleanup_free_to_play_games():
    """Clean up arbitrage opportunities involving free-to-play games"""
    try:
        session = Session()
        detector = ArbitrageDetector(session)
        count = detector.cleanup_free_to_play_opportunities()
        logger.info(f"Initial cleanup: removed {count} invalid opportunities for free-to-play games")
    except Exception as e:
        logger.error(f"Error during free-to-play games cleanup: {str(e)}")
    finally:
        session.close()

# Background task for monitoring prices
async def monitor_prices():
    """Monitor prices across marketplaces and detect arbitrage opportunities"""
    try:
        session = Session()
        
        # Initialize components
        steam_marketplace = session.query(Marketplace).filter_by(name="Steam").first()
        if not steam_marketplace:
            logger.error("Steam marketplace not found in database")
            return
            
        # Check if Epic Games marketplace exists, create if not
        epic_marketplace = session.query(Marketplace).filter_by(name="Epic Games").first()
        if not epic_marketplace:
            logger.info("Creating Epic Games marketplace record")
            epic_marketplace = Marketplace(
                name="Epic Games",
                base_url="https://www.epicgames.com/store/",
                api_enabled=False,
                scraping_enabled=True,
                active=True
            )
            session.add(epic_marketplace)
            session.commit()
            epic_marketplace = session.query(Marketplace).filter_by(name="Epic Games").first()
        
        steam_scraper = SteamScraper(steam_marketplace.id)
        arbitrage_detector = ArbitrageDetector(session)
        notification_system = NotificationSystem(session)
        
        # First, clean up any existing opportunities for free-to-play games
        cleanup_count = arbitrage_detector.cleanup_free_to_play_opportunities()
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} opportunities for free-to-play games")
        
        # For eager loading relationships
        from sqlalchemy.orm import joinedload

        # Get active products and update IDs before price monitoring
        products = session.query(Product).all()
        logger.info(f"Monitoring prices for {len(products)} products")
        
        # First, perform any needed ID updates
        # Dictionary to keep track of ID mappings (old ID -> new ID)
        id_updates = {
            "271590": "3240220",  # GTA V -> GTA V Enhanced
            "1938090": "2519060", # Old COD -> New COD
            "2118300": "2338770"  # Old NBA 2K24 -> New NBA 2K24
        }
        
        # Names for logging
        id_names = {
            "271590": "Grand Theft Auto V",
            "1938090": "Call of Duty: Modern Warfare III",
            "2118300": "NBA 2K24"
        }
        
        # URLs for updated products
        id_urls = {
            "3240220": "https://store.steampowered.com/app/3240220/Grand_Theft_Auto_V_Enhanced/",
            "2519060": "https://store.steampowered.com/app/2519060/Call_of_Duty_Modern_Warfare_III/",
            "2338770": "https://store.steampowered.com/app/2338770/NBA_2K24/"
        }
        
        # Update old IDs to new ones
        for product in products:
            product_metadata = product.product_metadata or {}
            old_id = product_metadata.get('steam_id', product.identifier)
            
            # Check if this product needs ID update
            if old_id in id_updates:
                new_id = id_updates[old_id]
                name = id_names.get(old_id, product.name)
                
                logger.info(f"Updating {name} from ID {old_id} to {new_id}")
                
                # Update product
                product.name = name + (" Enhanced" if old_id == "271590" else "")
                product.identifier = new_id
                
                # Update metadata
                new_metadata = product_metadata.copy() if product_metadata else {}
                new_metadata["steam_id"] = new_id
                new_metadata["url"] = id_urls.get(new_id, f"https://store.steampowered.com/app/{new_id}")
                product.product_metadata = new_metadata
        
        # Commit all ID updates before proceeding
        session.commit()
        logger.info("ID updates committed, proceeding with price monitoring")
        
        # Now refresh the product list to get the updated data
        products = session.query(Product).all()
        
        # Filter out free-to-play games
        filtered_products = []
        for product in products:
            # Check dynamically if it's free-to-play rather than using static list
            if product.id in FREE_TO_PLAY_CACHE and FREE_TO_PLAY_CACHE[product.id]:
                logger.debug(f"Skipping known free-to-play game: {product.name}")
                continue
            filtered_products.append(product)
            
        logger.info(f"Monitoring prices for {len(filtered_products)} products")
        
        # Track Steam prices to generate realistic Epic prices
        steam_prices = {}
        
        new_price_count = 0
        for product in filtered_products:
            try:
                # Check if product has metadata with Steam ID
                product_metadata = product.product_metadata or {}
                steam_id = product_metadata.get('steam_id', product.identifier)
                
                # Get URL from metadata if available, otherwise construct it
                if product_metadata and "url" in product_metadata and product_metadata["url"]:
                    product_url = product_metadata["url"]
                else:
                    # Construct product URL
                    product_url = f"https://store.steampowered.com/app/{steam_id}"
                    
                    # Special case URLs
                    if steam_id == "3240220":
                        product_url = "https://store.steampowered.com/app/3240220/Grand_Theft_Auto_V_Enhanced/"
                    elif steam_id == "2519060":
                        product_url = "https://store.steampowered.com/app/2519060/Call_of_Duty_Modern_Warfare_III/"
                    elif steam_id == "2338770":
                        product_url = "https://store.steampowered.com/app/2338770/NBA_2K24/"
                        
                logger.debug(f"Getting price for {product.name} from {product_url}")
                
                # Get current prices for EUR region
                price_data = steam_scraper.get_price(product_url, region='EU')
                
                if price_data:
                    # Check if this is a free-to-play game
                    if price_data.get('is_free', False):
                        logger.info(f"Skipping free-to-play game: {product.name}")
                        # Add to cache to avoid rechecking
                        FREE_TO_PLAY_CACHE[product.id] = True
                        continue
                        
                    # Ensure we're using EUR
                    if price_data['currency'] != 'EUR':
                        logger.warning(f"Currency mismatch for {product.name}: got {price_data['currency']} instead of EUR, forcing to EUR")
                        price_data['currency'] = 'EUR'
                    
                    logger.info(f"Got price for {product.name}: {price_data['currency']} {price_data['price']}")
                    
                    # Store for Epic Games price generation
                    steam_prices[product.id] = price_data['price']
                    
                    price_point = PricePoint(
                        product_id=product.id,
                        marketplace_id=steam_marketplace.id,
                        price=price_data['price'],
                        currency=price_data['currency'],
                        converted_price=price_data['price'],  # Already in EUR
                        region='EU',
                        url=product_url,
                        timestamp=datetime.utcnow()
                    )
                    
                    session.add(price_point)
                    new_price_count += 1
                else:
                    logger.warning(f"No price data found for {product.name}")
                
                # Avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error monitoring product {product.id} - {product.name}: {str(e)}")
        
        logger.info(f"Added {new_price_count} new price points")
        
        # Now generate Epic Games prices based on Steam prices
        epic_price_count = 0
        for product in filtered_products:
            # Create Epic Games price point with N/A value
            epic_url = f"https://www.epicgames.com/store/en-US/p/{product.name.lower().replace(' ', '-')}"
            
            # Use -1 as a placeholder for N/A pricing
            price_point = PricePoint(
                product_id=product.id,
                marketplace_id=epic_marketplace.id,
                price=-1.0,
                currency='EUR',
                converted_price=-1.0,  # Special value to indicate N/A
                region='EU',
                url=epic_url,
                timestamp=datetime.utcnow(),
                metadata={"status": "unavailable", "note": "Price unavailable - no API access"}
            )
            
            session.add(price_point)
            epic_price_count += 1
            
            logger.debug(f"Created Epic price for {product.name} as N/A (not available)")
        
        logger.info(f"Added {epic_price_count} Epic Games price points (all marked as N/A)")
        
        # Commit all price changes before detecting opportunities
        session.commit()
        
        # Detect arbitrage opportunities
        opportunities = arbitrage_detector.find_opportunities()
        logger.info(f"Found {len(opportunities)} new arbitrage opportunities")
        
        # Notify about new opportunities
        for opportunity in opportunities:
            session.add(opportunity)
            
            # Check if source_price and target_price exist
            if not opportunity.source_price or not opportunity.target_price:
                logger.error(f"Invalid opportunity data: opportunity has missing price data")
                continue
            
            # Validate that the necessary relationships are fully loaded
            try:
                # Try to access relationship attributes to force loading
                source_test = opportunity.source_price.product.name
                target_test = opportunity.target_price.product.name
                source_market = opportunity.source_price.marketplace.name
                target_market = opportunity.target_price.marketplace.name
            except Exception as e:
                logger.error(f"Failed to load relationship data: {str(e)}")
                continue
            
            try:
                # Handle currency conversion if needed
                source_price = opportunity.source_price.price
                target_price = opportunity.target_price.price
                
                source_currency = opportunity.source_price.currency
                target_currency = opportunity.target_price.currency
                
                # Convert to EUR if needed (only if not already EUR)
                if source_currency != 'EUR' and source_currency == 'USD':
                    source_price = source_price * 0.93
                    logger.debug(f"WebSocket: Converted source price from USD to EUR: {source_price}")
                    
                if target_currency != 'EUR' and target_currency == 'USD':
                    target_price = target_price * 0.93
                    logger.debug(f"WebSocket: Converted target price from USD to EUR: {target_price}")
                
                # Store original values before any potential swapping
                notification_opportunity = opportunity
                notification_source_name = opportunity.source_price.product.name if opportunity.source_price and opportunity.source_price.product else "Unknown Product"
                
                # FIX: In arbitrage, you buy at the lower price (target) and sell at the higher price (source)
                # So we need to ensure that in our data model, target_price is always lower than source_price
                # If not, we need to swap them to match UI expectations
                if target_price > source_price:
                    # Swap prices and marketplaces to maintain correct buy/sell relationship
                    source_price, target_price = target_price, source_price
                    source_marketplace = opportunity.target_price.marketplace.name if opportunity.target_price and opportunity.target_price.marketplace else "Unknown"
                    target_marketplace = opportunity.source_price.marketplace.name if opportunity.source_price and opportunity.source_price.marketplace else "Unknown"
                    logger.info(f"WebSocket: Swapped source/target for {notification_source_name} to maintain proper buy/sell relationship")
                else:
                    source_marketplace = opportunity.source_price.marketplace.name if opportunity.source_price and opportunity.source_price.marketplace else "Unknown"
                    target_marketplace = opportunity.target_price.marketplace.name if opportunity.target_price and opportunity.target_price.marketplace else "Unknown"
                
                # Send notification using the original opportunity data
                try:
                    await notification_system.notify_opportunity(notification_opportunity)
                except Exception as e:
                    logger.error(f"Failed to send notification for opportunity ({notification_source_name}): {str(e)}")
                
                socketio.emit('new_opportunity', {
                    'id': getattr(opportunity, 'id', 0),  # Use 0 as placeholder if ID not yet assigned
                    'product_name': notification_source_name,
                    'profit_margin': opportunity.profit_margin,
                    'absolute_profit': opportunity.absolute_profit,
                    'risk_score': opportunity.risk_score,
                    'source_marketplace': source_marketplace,
                    'target_marketplace': target_marketplace,
                    'source_price': {
                        'amount': source_price,
                        'currency': 'EUR'  # Always use EUR
                    },
                    'target_price': {
                        'amount': target_price,
                        'currency': 'EUR'  # Always use EUR
                    },
                    'detected_at': opportunity.detected_at.isoformat(),
                    'expires_at': opportunity.expires_at.isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing opportunity: {str(e)}")
        
        session.commit()
        
    except Exception as e:
        logger.error(f"Error in price monitoring task: {str(e)}")
        session.rollback()
    finally:
        session.close()

# Flask routes
@app.route('/')
def index():
    """Render dashboard"""
    return render_template('index.html')

@app.route('/api/opportunities')
def get_opportunities():
    """Get current arbitrage opportunities"""
    try:
        session = Session()
        
        # Only get opportunities created within the last 30 minutes to ensure freshness
        thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
        opportunities = session.query(ArbitrageOpportunity).options(
            joinedload(ArbitrageOpportunity.source_price).joinedload(PricePoint.product),
            joinedload(ArbitrageOpportunity.source_price).joinedload(PricePoint.marketplace),
            joinedload(ArbitrageOpportunity.target_price).joinedload(PricePoint.product),
            joinedload(ArbitrageOpportunity.target_price).joinedload(PricePoint.marketplace)
        ).filter(
            ArbitrageOpportunity.status == 'active',
            ArbitrageOpportunity.detected_at >= thirty_minutes_ago
        ).all()
        
        logger.info(f"Found {len(opportunities)} recent opportunities from the last 30 minutes")
        
        # If no recent opportunities, trigger a fresh scan
        if len(opportunities) == 0:
            logger.info("No recent opportunities found, triggering a fresh price scan")
            # Run price monitoring synchronously to get fresh data
            asyncio.run(monitor_prices())
            
            # Try again with fresh data
            opportunities = session.query(ArbitrageOpportunity).options(
                joinedload(ArbitrageOpportunity.source_price).joinedload(PricePoint.product),
                joinedload(ArbitrageOpportunity.source_price).joinedload(PricePoint.marketplace),
                joinedload(ArbitrageOpportunity.target_price).joinedload(PricePoint.product),
                joinedload(ArbitrageOpportunity.target_price).joinedload(PricePoint.marketplace)
            ).filter(
                ArbitrageOpportunity.status == 'active',
                ArbitrageOpportunity.detected_at >= thirty_minutes_ago
            ).all()
            logger.info(f"After fresh scan, found {len(opportunities)} opportunities")
        
        # Dictionary to store unique opportunities (one per product/marketplace pair)
        unique_opportunities = {}
        
        for opp in opportunities:
            # Create a unique key based on product and marketplace pair
            product_id = opp.source_price.product_id
            source_market_id = opp.source_price.marketplace_id
            target_market_id = opp.target_price.marketplace_id
            key = f"{product_id}_{source_market_id}_{target_market_id}"
            
            # Only keep the opportunity with the highest absolute profit
            if key not in unique_opportunities or opp.absolute_profit > unique_opportunities[key].absolute_profit:
                unique_opportunities[key] = opp
        
        # Convert to JSON response
        result = []
        for opp in unique_opportunities.values():
            try:
                # Verify all numbers are valid
                source_price = opp.source_price.price if opp.source_price else 0.0
                target_price = opp.target_price.price if opp.target_price else 0.0
                
                # Skip opportunities with N/A prices (-1)
                if source_price == -1 or target_price == -1:
                    logger.debug(f"Skipping opportunity with N/A price for API response")
                    continue
                    
                absolute_profit = opp.absolute_profit
                
                # Get product name
                product_name = opp.source_price.product.name if opp.source_price and opp.source_price.product else "Unknown Product"
                
                # Verify they're all in the same currency
                source_currency = opp.source_price.currency if opp.source_price else "EUR"
                target_currency = opp.target_price.currency if opp.target_price else "EUR"
                
                # Get marketplace names
                source_marketplace_name = opp.source_price.marketplace.name if opp.source_price and opp.source_price.marketplace else "Unknown Source"
                target_marketplace_name = opp.target_price.marketplace.name if opp.target_price and opp.target_price.marketplace else "Unknown Target"
                
                # Log the data for debugging
                logger.debug(f"Opportunity for {product_name}: " +
                            f"Source: {source_price} {source_currency} ({source_marketplace_name}), " +
                            f"Target: {target_price} {target_currency} ({target_marketplace_name}), " +
                            f"Profit: {absolute_profit} EUR")
                
                # Ensure all values are in EUR (only convert if not already EUR)
                if source_currency != 'EUR':
                    # Apply conversion (using the same factor as in frontend)
                    if source_currency == 'USD':
                        source_price = source_price * 0.93
                        logger.debug(f"Converted source price from USD to EUR: {source_price}")
                
                if target_currency != 'EUR':
                    # Apply conversion (using the same factor as in frontend)
                    if target_currency == 'USD':
                        target_price = target_price * 0.93
                        logger.debug(f"Converted target price from USD to EUR: {target_price}")
                
                # FIX: In arbitrage, you buy at the lower price (target) and sell at the higher price (source)
                # So we need to ensure that in our data model, target_price is always lower than source_price
                # If not, we need to swap them to match UI expectations
                if target_price > source_price:
                    # Swap prices and marketplaces to maintain correct buy/sell relationship
                    source_price, target_price = target_price, source_price
                    source_marketplace, target_marketplace = target_marketplace_name, source_marketplace_name
                    logger.info(f"Swapped source/target for {product_name} to maintain proper buy/sell relationship")
                else:
                    source_marketplace = source_marketplace_name
                    target_marketplace = target_marketplace_name
                
                result.append({
                    'id': opp.id,
                    'product_name': product_name,
                    'profit_margin': opp.profit_margin,
                    'absolute_profit': absolute_profit,
                    'risk_score': opp.risk_score,
                    'source_marketplace': source_marketplace,
                    'target_marketplace': target_marketplace,
                    'source_price': {
                        'amount': source_price,
                        'currency': 'EUR'
                    },
                    'target_price': {
                        'amount': target_price,
                        'currency': 'EUR'
                    },
                    'detected_at': opp.detected_at.isoformat(),
                    'expires_at': opp.expires_at.isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing opportunity {opp.id}: {str(e)}")
                # Skip this opportunity and continue with others
                continue
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching opportunities: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        session.close()

@app.route('/api/statistics')
def get_statistics():
    """Get system statistics"""
    try:
        session = Session()
        
        total_opportunities = session.query(ArbitrageOpportunity).count()
        active_opportunities = session.query(ArbitrageOpportunity).filter_by(status='active').count()
        total_profit = session.query(func.sum(ArbitrageOpportunity.absolute_profit)).filter_by(status='executed').scalar() or 0
        
        return jsonify({
            'total_opportunities': total_opportunities,
            'active_opportunities': active_opportunities,
            'total_profit': float(total_profit),
            'monitored_products': session.query(Product).count(),
            'last_update': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error fetching statistics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        session.close()

def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Add job to run every 2 minutes
    scheduler.add_job(
        lambda: asyncio.run(monitor_prices()),
        'interval',
        minutes=2,
        id='price_monitor'
    )
    
    # Schedule the same job to run immediately once on startup
    scheduler.add_job(
        lambda: asyncio.run(monitor_prices()),
        id='initial_price_monitor'
    )
    
    scheduler.start()
    logger.info("Background scheduler started")

if __name__ == '__main__':
    # Initialize components
    init_components()
    
    # Start background scheduler
    start_scheduler()
    
    # Run Flask application
    socketio.run(app, debug=FLASK_CONFIG['DEBUG'], allow_unsafe_werkzeug=True) 