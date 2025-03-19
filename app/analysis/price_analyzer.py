import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models import PricePoint, Product


class PriceAnalyzer:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger("price_analyzer")
        self._scaler = MinMaxScaler()

    def analyze_price_history(self, product_id: int, days: int = 30) -> Dict:
        """Analyze price history for a product"""
        try:
            # Get price history
            start_date = datetime.utcnow() - timedelta(days=days)
            price_points = self.session.query(PricePoint).filter(
                and_(
                    PricePoint.product_id == product_id,
                    PricePoint.timestamp >= start_date
                )
            ).order_by(PricePoint.timestamp.asc()).all()

            if not price_points:
                return self._empty_analysis_result()

            prices = [p.converted_price for p in price_points]
            timestamps = [p.timestamp for p in price_points]

            return {
                'basic_stats': self._calculate_basic_stats(prices),
                'trends': self._analyze_trends(prices, timestamps),
                'patterns': self._detect_patterns(prices),
                'seasonality': self._analyze_seasonality(prices, timestamps),
                'volatility': self._calculate_volatility(prices)
            }
        except Exception as e:
            self.logger.error(f"Error analyzing price history: {str(e)}")
            return self._empty_analysis_result()

    def predict_price_movement(self, product_id: int) -> Dict:
        """Predict future price movement based on historical data"""
        try:
            analysis = self.analyze_price_history(product_id)
            
            # Combine various factors for prediction
            prediction = {
                'direction': self._predict_direction(analysis),
                'confidence': self._calculate_prediction_confidence(analysis),
                'suggested_hold_time': self._suggest_hold_time(analysis),
                'risk_factors': self._identify_risk_factors(analysis)
            }

            return prediction
        except Exception as e:
            self.logger.error(f"Error predicting price movement: {str(e)}")
            return {
                'direction': 'unknown',
                'confidence': 0.0,
                'suggested_hold_time': 24,  # hours
                'risk_factors': []
            }

    def find_correlated_products(self, product_id: int, min_correlation: float = 0.7) -> List[Dict]:
        """Find products with correlated price movements"""
        try:
            # Get target product's price history
            target_prices = self._get_normalized_prices(product_id)
            if not target_prices:
                return []

            # Get all other products' prices
            all_products = self.session.query(Product).filter(
                Product.id != product_id
            ).all()

            correlations = []
            for product in all_products:
                other_prices = self._get_normalized_prices(product.id)
                if not other_prices:
                    continue

                # Calculate correlation if we have matching timeframes
                correlation = self._calculate_correlation(target_prices, other_prices)
                if correlation and abs(correlation) >= min_correlation:
                    correlations.append({
                        'product_id': product.id,
                        'correlation': correlation,
                        'strength': abs(correlation)
                    })

            return sorted(correlations, key=lambda x: x['strength'], reverse=True)
        except Exception as e:
            self.logger.error(f"Error finding correlated products: {str(e)}")
            return []

    def _calculate_basic_stats(self, prices: List[float]) -> Dict:
        """Calculate basic statistical measures"""
        return {
            'mean': float(np.mean(prices)),
            'median': float(np.median(prices)),
            'std': float(np.std(prices)),
            'min': float(np.min(prices)),
            'max': float(np.max(prices)),
            'current': float(prices[-1]) if prices else 0.0
        }

    def _analyze_trends(self, prices: List[float], timestamps: List[datetime]) -> Dict:
        """Analyze price trends"""
        if len(prices) < 2:
            return {'trend': 'neutral', 'strength': 0.0}

        # Calculate linear regression
        x = np.arange(len(prices))
        slope, _, r_value, _, _ = stats.linregress(x, prices)

        # Determine trend direction and strength
        trend = 'up' if slope > 0 else 'down' if slope < 0 else 'neutral'
        strength = abs(r_value)

        return {
            'trend': trend,
            'strength': float(strength),
            'slope': float(slope)
        }

    def _detect_patterns(self, prices: List[float]) -> Dict:
        """Detect common price patterns"""
        if len(prices) < 10:
            return {'patterns': []}

        patterns = []
        
        # Detect price reversals
        for i in range(2, len(prices)-2):
            # Local maximum (peak)
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                patterns.append({
                    'type': 'peak',
                    'position': i,
                    'value': prices[i]
                })
            
            # Local minimum (trough)
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                patterns.append({
                    'type': 'trough',
                    'position': i,
                    'value': prices[i]
                })

        return {'patterns': patterns}

    def _analyze_seasonality(self, prices: List[float], timestamps: List[datetime]) -> Dict:
        """Analyze seasonal patterns in price data"""
        if len(prices) < 24:  # Need at least 24 hours of data
            return {'has_seasonality': False}

        try:
            # Group prices by hour of day
            hourly_prices = {}
            for price, ts in zip(prices, timestamps):
                hour = ts.hour
                if hour not in hourly_prices:
                    hourly_prices[hour] = []
                hourly_prices[hour].append(price)

            # Calculate average price for each hour
            hourly_averages = {
                hour: np.mean(prices) for hour, prices in hourly_prices.items()
            }

            # Calculate variation in hourly averages
            variation = np.std(list(hourly_averages.values()))
            has_seasonality = variation > np.std(prices) * 0.1

            return {
                'has_seasonality': has_seasonality,
                'hourly_averages': hourly_averages,
                'variation': float(variation)
            }
        except Exception as e:
            self.logger.error(f"Error analyzing seasonality: {str(e)}")
            return {'has_seasonality': False}

    def _calculate_volatility(self, prices: List[float]) -> Dict:
        """Calculate price volatility metrics"""
        if len(prices) < 2:
            return {'volatility': 0.0}

        # Calculate returns
        returns = np.diff(prices) / prices[:-1]
        
        return {
            'volatility': float(np.std(returns)),
            'avg_daily_range': float(np.mean(np.abs(returns))),
            'max_drawdown': float(self._calculate_max_drawdown(prices))
        }

    def _calculate_max_drawdown(self, prices: List[float]) -> float:
        """Calculate maximum drawdown from peak"""
        peak = prices[0]
        max_drawdown = 0.0

        for price in prices[1:]:
            if price > peak:
                peak = price
            drawdown = (peak - price) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _predict_direction(self, analysis: Dict) -> str:
        """Predict price movement direction"""
        trend = analysis['trends']['trend']
        strength = analysis['trends']['strength']
        patterns = analysis['patterns']['patterns']
        
        if strength > 0.7:
            return trend
        elif patterns and patterns[-1]['type'] == 'trough':
            return 'up'
        elif patterns and patterns[-1]['type'] == 'peak':
            return 'down'
        else:
            return 'neutral'

    def _calculate_prediction_confidence(self, analysis: Dict) -> float:
        """Calculate confidence level in prediction"""
        factors = [
            analysis['trends']['strength'],
            1 - analysis['volatility']['volatility'],
            0.8 if analysis['seasonality']['has_seasonality'] else 0.5
        ]
        return float(np.mean(factors))

    def _suggest_hold_time(self, analysis: Dict) -> int:
        """Suggest optimal hold time in hours"""
        base_time = 24  # Default hold time

        # Adjust based on volatility
        volatility = analysis['volatility']['volatility']
        if volatility > 0.2:
            base_time *= 0.5
        elif volatility < 0.05:
            base_time *= 1.5

        # Adjust based on seasonality
        if analysis['seasonality']['has_seasonality']:
            base_time = min(base_time, 12)  # Shorter hold time for seasonal patterns

        return int(base_time)

    def _identify_risk_factors(self, analysis: Dict) -> List[str]:
        """Identify potential risk factors"""
        risks = []
        
        if analysis['volatility']['volatility'] > 0.15:
            risks.append('high_volatility')
        if analysis['volatility']['max_drawdown'] > 0.1:
            risks.append('large_drawdown_risk')
        if analysis['trends']['strength'] < 0.3:
            risks.append('weak_trend')
        if analysis['seasonality']['has_seasonality']:
            risks.append('seasonal_volatility')

        return risks

    def _get_normalized_prices(self, product_id: int) -> List[Tuple[datetime, float]]:
        """Get normalized price history for a product"""
        try:
            start_date = datetime.utcnow() - timedelta(days=30)
            prices = self.session.query(
                PricePoint.timestamp,
                PricePoint.converted_price
            ).filter(
                and_(
                    PricePoint.product_id == product_id,
                    PricePoint.timestamp >= start_date
                )
            ).order_by(PricePoint.timestamp.asc()).all()

            return [(p.timestamp, p.converted_price) for p in prices]
        except Exception as e:
            self.logger.error(f"Error getting normalized prices: {str(e)}")
            return []

    def _calculate_correlation(self, prices1: List[Tuple], prices2: List[Tuple]) -> Optional[float]:
        """Calculate correlation between two price series"""
        try:
            # Create price series with matching timestamps
            matched_prices = []
            for ts1, p1 in prices1:
                for ts2, p2 in prices2:
                    if abs((ts1 - ts2).total_seconds()) < 3600:  # Within 1 hour
                        matched_prices.append((p1, p2))
                        break

            if len(matched_prices) < 10:  # Need at least 10 matching points
                return None

            p1_series = [p[0] for p in matched_prices]
            p2_series = [p[1] for p in matched_prices]
            
            return float(np.corrcoef(p1_series, p2_series)[0, 1])
        except Exception as e:
            self.logger.error(f"Error calculating correlation: {str(e)}")
            return None

    def _empty_analysis_result(self) -> Dict:
        """Return empty analysis result structure"""
        return {
            'basic_stats': {
                'mean': 0.0, 'median': 0.0, 'std': 0.0,
                'min': 0.0, 'max': 0.0, 'current': 0.0
            },
            'trends': {'trend': 'neutral', 'strength': 0.0, 'slope': 0.0},
            'patterns': {'patterns': []},
            'seasonality': {'has_seasonality': False},
            'volatility': {'volatility': 0.0, 'avg_daily_range': 0.0, 'max_drawdown': 0.0}
        } 