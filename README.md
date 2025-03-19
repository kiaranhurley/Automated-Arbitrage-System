# Digital Marketplace Arbitrage System

A sophisticated system for monitoring and detecting arbitrage opportunities across digital marketplaces. The system continuously monitors product prices across various platforms, identifies profitable opportunities, and provides real-time notifications through multiple channels.

## Features

- **Multi-marketplace Monitoring**: Tracks prices across multiple digital marketplaces (Steam, GOG, etc.)
- **Real-time Arbitrage Detection**: Continuously analyzes price differences to identify profitable opportunities
- **Risk Assessment**: Sophisticated risk scoring system considering multiple factors
- **Multi-channel Notifications**: Email, Telegram, and Discord notifications for new opportunities
- **Web Dashboard**: Real-time visualization of opportunities and system statistics
- **Flexible Filtering**: Filter opportunities by profit margin, absolute profit, and risk level
- **Historical Analysis**: Track successful arbitrage operations and analyze patterns

## System Requirements

- Python 3.8+
- PostgreSQL 12+
- Redis (for background tasks)
- Modern web browser for dashboard access

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd digital-arbitrage-system
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file with your configuration:
- Database credentials
- API keys (Steam, GOG)
- Notification settings (Email, Telegram, Discord)
- Arbitrage parameters

5. Initialize the database:
```bash
python -c "from models import init_db; init_db()"
```

## Configuration

### Database Setup

1. Create a PostgreSQL database:
```sql
CREATE DATABASE arbitrage_db;
```

2. Update the database configuration in `.env`:
```
DB_NAME=arbitrage_db
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### Notification Setup

#### Email Notifications
1. Configure SMTP settings in `.env`:
```
EMAIL_ENABLED=True
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_specific_password
```

#### Telegram Notifications
1. Create a Telegram bot using BotFather
2. Configure Telegram settings in `.env`:
```
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

#### Discord Notifications
1. Create a Discord webhook in your server
2. Configure Discord settings in `.env`:
```
DISCORD_ENABLED=True
DISCORD_WEBHOOK_URL=your_webhook_url
```

### Arbitrage Parameters

Configure arbitrage detection parameters in `.env`:
```
MIN_PROFIT_MARGIN=10.0
MIN_ABSOLUTE_PROFIT=5.0
MAX_INVESTMENT=1000.0
MAX_HOLD_TIME=72
```

## Running the System

1. Start the Redis server:
```bash
redis-server
```

2. Start the web application:
```bash
python app.py
```

3. Access the dashboard at `http://localhost:5000`

## Architecture

The system consists of several key components:

### Data Collection
- `marketplace_scraper.py`: Base scraper class with common functionality
- `steam_scraper.py`: Steam-specific implementation
- Additional marketplace scrapers can be added following the same pattern

### Data Processing
- `arbitrage_detector.py`: Core logic for identifying arbitrage opportunities
- Risk assessment and profit calculation
- Historical data analysis

### Notification System
- `notification_system.py`: Handles multi-channel notifications
- Supports email, Telegram, and Discord
- Extensible for additional notification channels

### Web Interface
- Flask-based web application
- Real-time updates using WebSocket
- Responsive dashboard with filtering and sorting capabilities

## Database Schema

### Main Tables
- `marketplaces`: Marketplace information and configuration
- `products`: Product details and metadata
- `price_points`: Historical price data
- `arbitrage_opportunities`: Detected opportunities and their status
- `notification_logs`: Record of sent notifications

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Security Considerations

- Never commit sensitive credentials to version control
- Use environment variables for all sensitive configuration
- Implement rate limiting for API requests
- Monitor system resources and implement appropriate limits
- Regularly update dependencies for security patches

## Troubleshooting

### Common Issues

1. Database Connection Errors
   - Verify PostgreSQL is running
   - Check database credentials in `.env`
   - Ensure database exists and is accessible

2. Notification Failures
   - Verify API keys and tokens
   - Check network connectivity
   - Review notification logs in the database

3. Scraping Issues
   - Check rate limiting settings
   - Verify marketplace accessibility
   - Review scraper logs for errors

### Logging

Logs are stored in the `logs` directory:
- `arbitrage.log`: Main application log
- Check logs for detailed error information

## Future Enhancements

- Additional marketplace integrations
- Machine learning for price prediction
- Mobile application
- API for external integrations
- Advanced analytics and reporting
- Automated trading capabilities 