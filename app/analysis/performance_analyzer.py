import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models import ArbitrageOpportunity, NotificationLog


class PerformanceAnalyzer:
    def __init__(self, session: Session):
        self.session = session
        self.logger = logging.getLogger("performance_analyzer")

    def analyze_system_performance(self, days: int = 30) -> Dict:
        """Analyze overall system performance"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get opportunities data
            opportunities = self.session.query(ArbitrageOpportunity).filter(
                ArbitrageOpportunity.detected_at >= start_date
            ).all()

            # Calculate metrics
            return {
                'opportunity_metrics': self._analyze_opportunities(opportunities),
                'profit_metrics': self._analyze_profits(opportunities),
                'time_metrics': self._analyze_timing(opportunities),
                'risk_metrics': self._analyze_risks(opportunities),
                'notification_metrics': self._analyze_notifications(start_date)
            }
        except Exception as e:
            self.logger.error(f"Error analyzing system performance: {str(e)}")
            return self._empty_performance_result()

    def get_success_rate(self, days: int = 30) -> Dict:
        """Calculate success rate of identified opportunities"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            opportunities = self.session.query(ArbitrageOpportunity).filter(
                ArbitrageOpportunity.detected_at >= start_date
            ).all()

            total = len(opportunities)
            if total == 0:
                return {'success_rate': 0.0, 'total_opportunities': 0}

            successful = sum(1 for opp in opportunities if opp.status == 'successful')
            
            return {
                'success_rate': (successful / total) * 100,
                'total_opportunities': total,
                'successful_opportunities': successful,
                'failed_opportunities': total - successful
            }
        except Exception as e:
            self.logger.error(f"Error calculating success rate: {str(e)}")
            return {'success_rate': 0.0, 'total_opportunities': 0}

    def analyze_marketplace_performance(self, days: int = 30) -> List[Dict]:
        """Analyze performance by marketplace"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            opportunities = self.session.query(ArbitrageOpportunity).filter(
                ArbitrageOpportunity.detected_at >= start_date
            ).all()

            marketplace_stats = {}
            for opp in opportunities:
                source_id = opp.source_price.marketplace_id
                target_id = opp.target_price.marketplace_id

                # Initialize marketplace stats if not exists
                for m_id in [source_id, target_id]:
                    if m_id not in marketplace_stats:
                        marketplace_stats[m_id] = {
                            'marketplace_id': m_id,
                            'total_opportunities': 0,
                            'successful_opportunities': 0,
                            'total_profit': 0.0,
                            'average_profit_margin': 0.0,
                            'average_risk_score': 0.0
                        }

                # Update stats for both marketplaces
                for m_id in [source_id, target_id]:
                    stats = marketplace_stats[m_id]
                    stats['total_opportunities'] += 1
                    if opp.status == 'successful':
                        stats['successful_opportunities'] += 1
                        stats['total_profit'] += opp.absolute_profit
                    stats['average_profit_margin'] += opp.profit_margin
                    stats['average_risk_score'] += opp.risk_score

            # Calculate averages
            for stats in marketplace_stats.values():
                if stats['total_opportunities'] > 0:
                    stats['average_profit_margin'] /= stats['total_opportunities']
                    stats['average_risk_score'] /= stats['total_opportunities']
                    stats['success_rate'] = (stats['successful_opportunities'] / 
                                           stats['total_opportunities'] * 100)

            return list(marketplace_stats.values())
        except Exception as e:
            self.logger.error(f"Error analyzing marketplace performance: {str(e)}")
            return []

    def _analyze_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Analyze opportunity metrics"""
        total = len(opportunities)
        if total == 0:
            return {
                'total': 0,
                'daily_average': 0.0,
                'success_rate': 0.0
            }

        successful = sum(1 for opp in opportunities if opp.status == 'successful')
        days_span = (max(opp.detected_at for opp in opportunities) -
                    min(opp.detected_at for opp in opportunities)).days or 1

        return {
            'total': total,
            'daily_average': total / days_span,
            'success_rate': (successful / total) * 100
        }

    def _analyze_profits(self, opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Analyze profit metrics"""
        if not opportunities:
            return {
                'total_profit': 0.0,
                'average_profit': 0.0,
                'average_margin': 0.0,
                'best_profit': 0.0
            }

        successful_opps = [opp for opp in opportunities if opp.status == 'successful']
        if not successful_opps:
            return {
                'total_profit': 0.0,
                'average_profit': 0.0,
                'average_margin': 0.0,
                'best_profit': 0.0
            }

        profits = [opp.absolute_profit for opp in successful_opps]
        margins = [opp.profit_margin for opp in successful_opps]

        return {
            'total_profit': sum(profits),
            'average_profit': np.mean(profits),
            'average_margin': np.mean(margins),
            'best_profit': max(profits)
        }

    def _analyze_timing(self, opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Analyze timing metrics"""
        if not opportunities:
            return {
                'average_duration': 0.0,
                'fastest_execution': 0.0,
                'slowest_execution': 0.0
            }

        successful_opps = [opp for opp in opportunities if opp.status == 'successful']
        if not successful_opps:
            return {
                'average_duration': 0.0,
                'fastest_execution': 0.0,
                'slowest_execution': 0.0
            }

        durations = [(opp.completed_at - opp.detected_at).total_seconds() / 3600
                    for opp in successful_opps if opp.completed_at]

        if not durations:
            return {
                'average_duration': 0.0,
                'fastest_execution': 0.0,
                'slowest_execution': 0.0
            }

        return {
            'average_duration': np.mean(durations),
            'fastest_execution': min(durations),
            'slowest_execution': max(durations)
        }

    def _analyze_risks(self, opportunities: List[ArbitrageOpportunity]) -> Dict:
        """Analyze risk metrics"""
        if not opportunities:
            return {
                'average_risk_score': 0.0,
                'risk_success_correlation': 0.0
            }

        risk_scores = [opp.risk_score for opp in opportunities]
        success_values = [1.0 if opp.status == 'successful' else 0.0 
                         for opp in opportunities]

        correlation = np.corrcoef(risk_scores, success_values)[0, 1]

        return {
            'average_risk_score': np.mean(risk_scores),
            'risk_success_correlation': float(correlation)
        }

    def _analyze_notifications(self, start_date: datetime) -> Dict:
        """Analyze notification system performance"""
        try:
            notifications = self.session.query(NotificationLog).filter(
                NotificationLog.timestamp >= start_date
            ).all()

            if not notifications:
                return {
                    'total_sent': 0,
                    'success_rate': 0.0,
                    'average_delay': 0.0
                }

            total = len(notifications)
            successful = sum(1 for n in notifications if n.status == 'success')
            delays = [(n.timestamp - n.opportunity.detected_at).total_seconds()
                     for n in notifications if n.opportunity]

            return {
                'total_sent': total,
                'success_rate': (successful / total) * 100 if total > 0 else 0.0,
                'average_delay': np.mean(delays) if delays else 0.0
            }
        except Exception as e:
            self.logger.error(f"Error analyzing notifications: {str(e)}")
            return {
                'total_sent': 0,
                'success_rate': 0.0,
                'average_delay': 0.0
            }

    def _empty_performance_result(self) -> Dict:
        """Return empty performance analysis result"""
        return {
            'opportunity_metrics': {
                'total': 0,
                'daily_average': 0.0,
                'success_rate': 0.0
            },
            'profit_metrics': {
                'total_profit': 0.0,
                'average_profit': 0.0,
                'average_margin': 0.0,
                'best_profit': 0.0
            },
            'time_metrics': {
                'average_duration': 0.0,
                'fastest_execution': 0.0,
                'slowest_execution': 0.0
            },
            'risk_metrics': {
                'average_risk_score': 0.0,
                'risk_success_correlation': 0.0
            },
            'notification_metrics': {
                'total_sent': 0,
                'success_rate': 0.0,
                'average_delay': 0.0
            }
        } 