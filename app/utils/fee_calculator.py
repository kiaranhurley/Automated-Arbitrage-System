import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from models import Marketplace


class FeeCalculator:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger("fee_calculator")
        self._fee_configs = self._load_fee_configs()

    def _load_fee_configs(self) -> Dict[int, Dict]:
        """Load fee configurations for all marketplaces"""
        configs = {}
        try:
            marketplaces = self.session.query(Marketplace).all()
            for marketplace in marketplaces:
                if marketplace.config and 'fees' in marketplace.config:
                    configs[marketplace.id] = marketplace.config['fees']
        except Exception as e:
            self.logger.error(f"Error loading fee configurations: {str(e)}")
        return configs

    def calculate_fees(self, marketplace_id: int, price: float) -> Dict[str, float]:
        """Calculate all applicable fees for a given price on a marketplace"""
        try:
            if marketplace_id not in self._fee_configs:
                return {'total': 0.0, 'breakdown': {}}

            fees = self._fee_configs[marketplace_id]
            breakdown = {}
            total_fee = 0.0

            # Platform fee
            if 'platform_fee' in fees:
                platform_fee = price * (fees['platform_fee'] / 100)
                breakdown['platform_fee'] = platform_fee
                total_fee += platform_fee

            # Transaction fee
            if 'transaction_fee' in fees:
                if 'fixed' in fees['transaction_fee']:
                    transaction_fee = fees['transaction_fee']['fixed']
                else:
                    transaction_fee = price * (fees['transaction_fee']['percentage'] / 100)
                breakdown['transaction_fee'] = transaction_fee
                total_fee += transaction_fee

            # Payment processing fee
            if 'payment_fee' in fees:
                payment_fee = price * (fees['payment_fee'] / 100)
                breakdown['payment_fee'] = payment_fee
                total_fee += payment_fee

            return {
                'total': total_fee,
                'breakdown': breakdown
            }

        except Exception as e:
            self.logger.error(f"Error calculating fees: {str(e)}")
            return {'total': 0.0, 'breakdown': {}}

    def calculate_net_profit(self, buy_price: float, sell_price: float,
                           source_marketplace_id: int, target_marketplace_id: int) -> Dict[str, float]:
        """Calculate net profit after all fees"""
        try:
            # Calculate fees for both buy and sell
            buy_fees = self.calculate_fees(target_marketplace_id, buy_price)
            sell_fees = self.calculate_fees(source_marketplace_id, sell_price)

            # Calculate gross profit
            gross_profit = sell_price - buy_price

            # Calculate total fees
            total_fees = buy_fees['total'] + sell_fees['total']

            # Calculate net profit
            net_profit = gross_profit - total_fees

            return {
                'gross_profit': gross_profit,
                'total_fees': total_fees,
                'net_profit': net_profit,
                'fee_breakdown': {
                    'buy_fees': buy_fees['breakdown'],
                    'sell_fees': sell_fees['breakdown']
                }
            }

        except Exception as e:
            self.logger.error(f"Error calculating net profit: {str(e)}")
            return {
                'gross_profit': 0.0,
                'total_fees': 0.0,
                'net_profit': 0.0,
                'fee_breakdown': {}
            } 