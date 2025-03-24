import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import ExchangeRate
from config import BASE_CURRENCY


class CurrencyConverter:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger("currency_converter")
        self._cache = {}
        self._cache_duration = timedelta(hours=1)

    def convert(self, amount: float, from_currency: str, to_currency: str = BASE_CURRENCY) -> Optional[float]:
        """Convert amount from one currency to another"""
        # Handle invalid inputs
        if amount is None:
            self.logger.warning("Cannot convert None amount")
            return None
            
        if from_currency is None or to_currency is None:
            self.logger.warning(f"Invalid currency: from={from_currency}, to={to_currency}")
            return None
        
        # No conversion needed if currencies are the same
        if from_currency == to_currency:
            return amount

        try:
            # Check if we have the rate in our fallback cache
            fallback_key = f"{from_currency}_{to_currency}"
            if hasattr(self, '_fallback_cache') and fallback_key in self._fallback_cache:
                return amount * self._fallback_cache[fallback_key]

            rate = self._get_exchange_rate(from_currency, to_currency)
            if rate is None:
                # If we don't have a rate in the database, use common fallbacks
                if from_currency == 'USD' and to_currency == 'EUR':
                    # Use DEBUG level instead of INFO to reduce log spam
                    self.logger.debug("Using fallback rate for USD to EUR: 0.93")
                    # Store in fallback cache to avoid repeated logging
                    if not hasattr(self, '_fallback_cache'):
                        self._fallback_cache = {}
                    self._fallback_cache[fallback_key] = 0.93
                    return amount * 0.93
                elif from_currency == 'EUR' and to_currency == 'USD':
                    self.logger.debug("Using fallback rate for EUR to USD: 1.08")
                    if not hasattr(self, '_fallback_cache'):
                        self._fallback_cache = {}
                    self._fallback_cache[fallback_key] = 1.08
                    return amount * 1.08
                else:
                    self.logger.warning(f"No exchange rate found for {from_currency} to {to_currency}")
                    return None
            return amount * rate
        except Exception as e:
            self.logger.error(f"Error converting currency: {str(e)}")
            return None

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate from cache or database"""
        cache_key = f"{from_currency}_{to_currency}"
        
        # Check cache
        if cache_key in self._cache:
            rate_data = self._cache[cache_key]
            if datetime.utcnow() - rate_data['timestamp'] < self._cache_duration:
                return rate_data['rate']

        # Query database
        rate = self.session.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.timestamp >= datetime.utcnow() - self._cache_duration
        ).order_by(ExchangeRate.timestamp.desc()).first()

        if rate:
            # Update cache
            self._cache[cache_key] = {
                'rate': rate.rate,
                'timestamp': rate.timestamp
            }
            return rate.rate

        return None

    def update_rate(self, from_currency: str, to_currency: str, rate: float) -> None:
        """Update exchange rate in database and cache"""
        try:
            new_rate = ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                timestamp=datetime.utcnow()
            )
            self.session.add(new_rate)
            self.session.commit()

            # Update cache
            cache_key = f"{from_currency}_{to_currency}"
            self._cache[cache_key] = {
                'rate': rate,
                'timestamp': datetime.utcnow()
            }
        except Exception as e:
            self.logger.error(f"Error updating exchange rate: {str(e)}")
            self.session.rollback() 