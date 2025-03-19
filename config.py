import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Database configurations
DATABASE_CONFIG = {
    'default': {
        'ENGINE': 'postgresql',
        'NAME': os.getenv('DB_NAME', 'arbitrage_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# API Keys and External Services
STEAM_API_KEY = os.getenv('STEAM_API_KEY', '')
GOG_API_KEY = os.getenv('GOG_API_KEY', '')
EXCHANGE_RATE_API_KEY = os.getenv('EXCHANGE_RATE_API_KEY', '')

# Notification Settings
NOTIFICATION_CONFIG = {
    'email': {
        'enabled': bool(os.getenv('EMAIL_ENABLED', True)),
        'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.getenv('SMTP_PORT', 587)),
        'sender_email': os.getenv('SENDER_EMAIL', ''),
        'sender_password': os.getenv('SENDER_PASSWORD', ''),
    },
    'telegram': {
        'enabled': bool(os.getenv('TELEGRAM_ENABLED', False)),
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
        'chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    },
    'discord': {
        'enabled': bool(os.getenv('DISCORD_ENABLED', False)),
        'webhook_url': os.getenv('DISCORD_WEBHOOK_URL', ''),
    }
}

# Arbitrage Settings
ARBITRAGE_CONFIG = {
    'min_profit_margin': float(os.getenv('MIN_PROFIT_MARGIN', 10.0)),  # percentage
    'min_absolute_profit': float(os.getenv('MIN_ABSOLUTE_PROFIT', 5.0)),  # in base currency
    'max_investment': float(os.getenv('MAX_INVESTMENT', 1000.0)),
    'max_hold_time': int(os.getenv('MAX_HOLD_TIME', 72)),  # hours
}

# Supported Currencies
BASE_CURRENCY = 'USD'
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'AUD', 'CAD']

# Web Scraping Settings
SCRAPING_CONFIG = {
    'max_retries': 3,
    'timeout': 30,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'request_delay': 2,  # seconds between requests
}

# Redis Configuration for Celery
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Flask Configuration
FLASK_CONFIG = {
    'SECRET_KEY': os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here'),
    'DEBUG': bool(os.getenv('FLASK_DEBUG', False)),
}

# Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'arbitrage.log'),
            'mode': 'a',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
} 