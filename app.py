import asyncio
import logging
import urllib.parse
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.core.arbitrage_detector import ArbitrageDetector
from app.marketplace.steam_scraper import SteamScraper
from app.models.models import (ArbitrageOpportunity, Marketplace, PricePoint,
                               Product, init_db)
from app.notifications.notification_system import NotificationSystem
from config import DATABASE_CONFIG, FLASK_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
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
        # Initialize database
        init_db()
        
        # Create session
        session = Session()
        
        # Initialize marketplace records if they don't exist
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
        
        session.close()
        logger.info("System components initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {str(e)}")
        raise

# Background task for monitoring prices
async def monitor_prices():
    """Monitor prices across marketplaces and detect arbitrage opportunities"""
    try:
        session = Session()
        
        # Initialize components
        steam_marketplace = session.query(Marketplace).filter_by(name="Steam").first()
        steam_scraper = SteamScraper(steam_marketplace.id)
        arbitrage_detector = ArbitrageDetector(session)
        notification_system = NotificationSystem(session)
        
        # Get active products
        products = session.query(Product).all()
        
        for product in products:
            try:
                # Get current prices
                price_data = steam_scraper.get_price(product.identifier)
                if price_data:
                    price_point = steam_scraper.create_price_point(
                        product.id,
                        price_data['price'],
                        price_data['currency'],
                        'US',
                        price_data.get('url')
                    )
                    session.add(price_point)
            except Exception as e:
                logger.error(f"Error monitoring product {product.id}: {str(e)}")
        
        session.commit()
        
        # Detect arbitrage opportunities
        opportunities = arbitrage_detector.find_opportunities()
        
        # Notify about new opportunities
        for opportunity in opportunities:
            session.add(opportunity)
            await notification_system.notify_opportunity(opportunity)
            
            # Emit to websocket clients
            socketio.emit('new_opportunity', {
                'id': opportunity.id,
                'profit_margin': opportunity.profit_margin,
                'absolute_profit': opportunity.absolute_profit,
                'risk_score': opportunity.risk_score,
                'detected_at': opportunity.detected_at.isoformat()
            })
        
        session.commit()
        
    except Exception as e:
        logger.error(f"Error in price monitoring task: {str(e)}")
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
        opportunities = session.query(ArbitrageOpportunity).filter_by(status='active').all()
        
        return jsonify([{
            'id': opp.id,
            'product_name': opp.source_price.product.name,
            'profit_margin': opp.profit_margin,
            'absolute_profit': opp.absolute_profit,
            'risk_score': opp.risk_score,
            'source_marketplace': opp.source_price.marketplace.name,
            'target_marketplace': opp.target_price.marketplace.name,
            'source_price': {
                'amount': opp.source_price.price,
                'currency': opp.source_price.currency
            },
            'target_price': {
                'amount': opp.target_price.price,
                'currency': opp.target_price.currency
            },
            'detected_at': opp.detected_at.isoformat(),
            'expires_at': opp.expires_at.isoformat()
        } for opp in opportunities])
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
    scheduler.add_job(
        lambda: asyncio.run(monitor_prices()),
        'interval',
        minutes=5,
        id='price_monitor'
    )
    scheduler.start()
    logger.info("Background scheduler started")

if __name__ == '__main__':
    # Initialize components
    init_components()
    
    # Start background scheduler
    start_scheduler()
    
    # Run Flask application
    socketio.run(app, debug=FLASK_CONFIG['DEBUG']) 