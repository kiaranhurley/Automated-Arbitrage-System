import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_CONFIG = {
    'default': {
        'NAME': os.getenv('DB_NAME', 'arbitrage_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Flask configuration
FLASK_CONFIG = {
    'SECRET_KEY': os.getenv('SECRET_KEY', 'dev_key'),
    'DEBUG': os.getenv('DEBUG', 'True').lower() == 'true',
}

# Currency configuration
BASE_CURRENCY = os.getenv('BASE_CURRENCY', 'USD')

# Arbitrage configuration
ARBITRAGE_CONFIG = {
    'min_profit_margin': float(os.getenv('MIN_PROFIT_MARGIN', '10.0')),
    'min_absolute_profit': float(os.getenv('MIN_ABSOLUTE_PROFIT', '5.0')),
    'max_investment': float(os.getenv('MAX_INVESTMENT', '1000.0')),
    'max_hold_time': int(os.getenv('MAX_HOLD_TIME', '72')),
}

# API Keys
STEAM_API_KEY = os.getenv('STEAM_API_KEY', '')
COINBASE_API_KEY = os.getenv('COINBASE_API_KEY', '')
COINBASE_API_SECRET = os.getenv('COINBASE_API_SECRET', '')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET', '')
EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY', '')

# Notification configuration
NOTIFICATION_CONFIG = {
    'email': {
        'enabled': os.getenv('EMAIL_ENABLED', 'False').lower() == 'true',
        'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.getenv('SMTP_PORT', '587')),
        'sender_email': os.getenv('SENDER_EMAIL', ''),
        'sender_password': os.getenv('SENDER_PASSWORD', '')
    },
    'telegram': {
        'enabled': os.getenv('TELEGRAM_ENABLED', 'False').lower() == 'true',
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
    },
    'discord': {
        'enabled': os.getenv('DISCORD_ENABLED', 'False').lower() == 'true',
        'webhook_url': os.getenv('DISCORD_WEBHOOK_URL', '')
    }
}

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Scraping configuration
SCRAPING_CONFIG = {
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'timeout': 30,
    'max_retries': 3,
    'request_delay': 1.0,
    'use_proxy': False,
    'proxy_list': []
}

# Add other configuration variables as needed
