import urllib.parse
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from config import DATABASE_CONFIG

Base = declarative_base()

class Marketplace(Base):
    __tablename__ = 'marketplaces'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    base_url = Column(String(255), nullable=False)
    api_enabled = Column(Boolean, default=False)
    scraping_enabled = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    config = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), nullable=False, unique=True)
    description = Column(String(1000))
    category = Column(String(100))
    product_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PricePoint(Base):
    __tablename__ = 'price_points'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    marketplace_id = Column(Integer, ForeignKey('marketplaces.id'), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    converted_price = Column(Float, nullable=False)  # Price in base currency (USD)
    region = Column(String(50), nullable=False)
    url = Column(String(500))
    in_stock = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", backref="price_points")
    marketplace = relationship("Marketplace", backref="price_points")

class ArbitrageOpportunity(Base):
    __tablename__ = 'arbitrage_opportunities'
    
    id = Column(Integer, primary_key=True)
    source_price_id = Column(Integer, ForeignKey('price_points.id'), nullable=False)
    target_price_id = Column(Integer, ForeignKey('price_points.id'), nullable=False)
    profit_margin = Column(Float, nullable=False)  # Percentage
    absolute_profit = Column(Float, nullable=False)  # In base currency
    risk_score = Column(Float)  # 0-1 scale
    status = Column(String(20), default='active')  # active, expired, executed
    detected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    executed_at = Column(DateTime)
    
    source_price = relationship("PricePoint", foreign_keys=[source_price_id])
    target_price = relationship("PricePoint", foreign_keys=[target_price_id])

class NotificationLog(Base):
    __tablename__ = 'notification_logs'
    
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey('arbitrage_opportunities.id'))
    channel = Column(String(50), nullable=False)  # email, telegram, discord
    status = Column(String(20), nullable=False)  # sent, failed
    error_message = Column(String(500))
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    opportunity = relationship("ArbitrageOpportunity", backref="notifications")

class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    
    id = Column(Integer, primary_key=True)
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

def init_db():
    """Initialize the database with tables"""
    # URL encode the password to handle special characters
    password = urllib.parse.quote_plus(DATABASE_CONFIG['default']['PASSWORD'])
    
    db_url = f"postgresql://{DATABASE_CONFIG['default']['USER']}:{password}@{DATABASE_CONFIG['default']['HOST']}:{DATABASE_CONFIG['default']['PORT']}/{DATABASE_CONFIG['default']['NAME']}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return engine 