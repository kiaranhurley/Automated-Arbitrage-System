import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import BASE_CURRENCY
from models import ExchangeRate


class CurrencyConverter:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger("currency_converter")
        self._cache = {}
        self._cache_duration = timedelta(hours=1)

    def convert(self, amount: float, from_currency: str, to_currency: str = BASE_CURRENCY) -> Optional[float]:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount

        try:
            rate = self._get_exchange_rate(from_currency, to_currency)
            if rate is None:
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