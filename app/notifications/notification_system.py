import asyncio
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

import aiohttp
import telegram

from app.models.models import ArbitrageOpportunity, NotificationLog
from config import NOTIFICATION_CONFIG


class NotificationSystem:
    def __init__(self, db_session):
        self.session = db_session
        self.logger = logging.getLogger("notification_system")
        self.config = NOTIFICATION_CONFIG

    async def notify_opportunity(self, opportunity: ArbitrageOpportunity):
        """Send notifications about a new arbitrage opportunity through all enabled channels"""
        notification_tasks = []
        
        if self.config['email']['enabled']:
            notification_tasks.append(self._send_email_notification(opportunity))
            
        if self.config['telegram']['enabled']:
            notification_tasks.append(self._send_telegram_notification(opportunity))
            
        if self.config['discord']['enabled']:
            notification_tasks.append(self._send_discord_notification(opportunity))

        try:
            # Run all notifications concurrently
            await asyncio.gather(*notification_tasks)
        except Exception as e:
            self.logger.error(f"Error sending notifications: {str(e)}")

    async def _send_email_notification(self, opportunity: ArbitrageOpportunity):
        """Send email notification about an arbitrage opportunity"""
        try:
            email_config = self.config['email']
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['sender_email']  # Could be configured for multiple recipients
            msg['Subject'] = f"New Arbitrage Opportunity - {opportunity.profit_margin:.2f}% Profit"
            
            # Create HTML content
            html_content = self._create_opportunity_html(opportunity)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['sender_email'], email_config['sender_password'])
                server.send_message(msg)
            
            self._log_notification(opportunity.id, 'email', 'sent')
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {str(e)}")
            self._log_notification(opportunity.id, 'email', 'failed', str(e))

    async def _send_telegram_notification(self, opportunity: ArbitrageOpportunity):
        """Send Telegram notification about an arbitrage opportunity"""
        try:
            telegram_config = self.config['telegram']
            bot = telegram.Bot(token=telegram_config['bot_token'])
            
            # Create message text
            message = self._create_opportunity_text(opportunity)
            
            # Send message
            await bot.send_message(
                chat_id=telegram_config['chat_id'],
                text=message,
                parse_mode='HTML'
            )
            
            self._log_notification(opportunity.id, 'telegram', 'sent')
            
        except Exception as e:
            self.logger.error(f"Failed to send Telegram notification: {str(e)}")
            self._log_notification(opportunity.id, 'telegram', 'failed', str(e))

    async def _send_discord_notification(self, opportunity: ArbitrageOpportunity):
        """Send Discord notification about an arbitrage opportunity"""
        try:
            discord_config = self.config['discord']
            webhook_url = discord_config['webhook_url']
            
            # Create embed
            embed = self._create_discord_embed(opportunity)
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=embed) as response:
                    if response.status == 204:
                        self._log_notification(opportunity.id, 'discord', 'sent')
                    else:
                        raise Exception(f"Discord webhook failed with status {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send Discord notification: {str(e)}")
            self._log_notification(opportunity.id, 'discord', 'failed', str(e))

    def _create_opportunity_html(self, opportunity: ArbitrageOpportunity) -> str:
        """Create HTML content for email notification"""
        source_price = opportunity.source_price
        target_price = opportunity.target_price
        
        return f"""
        <html>
            <body>
                <h2>New Arbitrage Opportunity Detected</h2>
                <p><strong>Product:</strong> {source_price.product.name}</p>
                <p><strong>Profit Margin:</strong> {opportunity.profit_margin:.2f}%</p>
                <p><strong>Absolute Profit:</strong> ${opportunity.absolute_profit:.2f}</p>
                <p><strong>Risk Score:</strong> {opportunity.risk_score:.2f}</p>
                <h3>Price Details:</h3>
                <ul>
                    <li>Buy from {target_price.marketplace.name} at {target_price.currency} {target_price.price:.2f}</li>
                    <li>Sell on {source_price.marketplace.name} at {source_price.currency} {source_price.price:.2f}</li>
                </ul>
                <p><strong>Expires:</strong> {opportunity.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><a href="{target_price.url}">View Buy Listing</a> | <a href="{source_price.url}">View Sell Listing</a></p>
            </body>
        </html>
        """

    def _create_opportunity_text(self, opportunity: ArbitrageOpportunity) -> str:
        """Create text content for Telegram notification"""
        source_price = opportunity.source_price
        target_price = opportunity.target_price
        
        return f"""
🎮 <b>New Arbitrage Opportunity</b>

Product: {source_price.product.name}
Profit Margin: {opportunity.profit_margin:.2f}%
Absolute Profit: ${opportunity.absolute_profit:.2f}
Risk Score: {opportunity.risk_score:.2f}

💰 Buy from {target_price.marketplace.name}
Price: {target_price.currency} {target_price.price:.2f}
{target_price.url}

📈 Sell on {source_price.marketplace.name}
Price: {source_price.currency} {source_price.price:.2f}
{source_price.url}

⏰ Expires: {opportunity.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
        """

    def _create_discord_embed(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Create Discord embed for webhook"""
        source_price = opportunity.source_price
        target_price = opportunity.target_price
        
        return {
            "embeds": [{
                "title": "New Arbitrage Opportunity",
                "description": f"Product: {source_price.product.name}",
                "color": 3066993,  # Green color
                "fields": [
                    {
                        "name": "Profit Details",
                        "value": f"Margin: {opportunity.profit_margin:.2f}%\nProfit: ${opportunity.absolute_profit:.2f}\nRisk Score: {opportunity.risk_score:.2f}",
                        "inline": False
                    },
                    {
                        "name": "Buy Details",
                        "value": f"Marketplace: {target_price.marketplace.name}\nPrice: {target_price.currency} {target_price.price:.2f}\n[View Listing]({target_price.url})",
                        "inline": True
                    },
                    {
                        "name": "Sell Details",
                        "value": f"Marketplace: {source_price.marketplace.name}\nPrice: {source_price.currency} {source_price.price:.2f}\n[View Listing]({source_price.url})",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": f"Expires at {opportunity.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }]
        }

    def _log_notification(self, opportunity_id: int, channel: str, status: str, error_message: str = None):
        """Log notification attempt to database"""
        try:
            log = NotificationLog(
                opportunity_id=opportunity_id,
                channel=channel,
                status=status,
                error_message=error_message,
                sent_at=datetime.utcnow()
            )
            self.session.add(log)
            self.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log notification: {str(e)}")
            self.session.rollback() 