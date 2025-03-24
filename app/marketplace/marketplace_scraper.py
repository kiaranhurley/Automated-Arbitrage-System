import logging
from abc import ABC, abstractmethod
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.models.models import PricePoint, Product
from config import SCRAPING_CONFIG


class MarketplaceScraper(ABC):
    def __init__(self, marketplace_id, name, base_url, session=None):
        self.marketplace_id = marketplace_id
        self.name = name
        self.base_url = base_url
        self.session = session or requests.Session()
        self.logger = logging.getLogger(f"scraper.{name}")
        
        # Configure session
        self.session.headers.update({
            'User-Agent': SCRAPING_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    @abstractmethod
    def search_products(self, query):
        """Search for products in the marketplace"""
        pass

    @abstractmethod
    def get_product_details(self, product_url):
        """Get detailed information about a product"""
        pass

    @abstractmethod
    def get_price(self, product_url, region=None):
        """Get the current price for a product"""
        pass

    def _make_request(self, url, method='get', data=None, headers=None, params=None, use_playwright=False):
        """Make an HTTP request with retry logic and optional JavaScript rendering"""
        for attempt in range(SCRAPING_CONFIG['max_retries']):
            try:
                if use_playwright:
                    return self._playwright_request(url, headers)
                else:
                    response = getattr(self.session, method)(
                        url,
                        data=data,
                        headers=headers,
                        params=params,
                        timeout=SCRAPING_CONFIG['timeout']
                    )
                    response.raise_for_status()
                    return response
            except Exception as e:
                self.logger.warning(f"Request failed (attempt {attempt + 1}): {str(e)}")
                if attempt == SCRAPING_CONFIG['max_retries'] - 1:
                    raise

    def _playwright_request(self, url, headers=None):
        """Make a request using Playwright for JavaScript-heavy pages"""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                user_agent=SCRAPING_CONFIG['user_agent'],
                extra_http_headers=headers or {}
            )
            page = context.new_page()
            page.goto(url, wait_until='networkidle')
            content = page.content()
            browser.close()
            return content

    def _parse_html(self, content):
        """Parse HTML content with BeautifulSoup"""
        return BeautifulSoup(content, 'html.parser')

    def _clean_price(self, price_str):
        """Clean and standardize price string to float"""
        try:
            # Remove currency symbols and whitespace
            cleaned = ''.join(c for c in price_str if c.isdigit() or c in '.,')
            # Handle different decimal separators
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            self.logger.error(f"Failed to parse price: {price_str}")
            return None

    def create_price_point(self, product_id, price, currency, region, url=None):
        """Create a PricePoint object with current data"""
        return PricePoint(
            product_id=product_id,
            marketplace_id=self.marketplace_id,
            price=price,
            currency=currency,
            region=region,
            url=url,
            timestamp=datetime.utcnow()
        )

    def validate_product_data(self, data):
        """Validate product data before creating/updating records"""
        required_fields = ['name', 'identifier']
        return all(field in data and data[field] for field in required_fields)

    def handle_rate_limit(self):
        """Handle rate limiting by implementing delay"""
        import time
        time.sleep(SCRAPING_CONFIG['request_delay'])

    @abstractmethod
    def extract_product_info(self, html):
        """Extract product information from HTML content"""
        pass

    @abstractmethod
    def extract_price_info(self, html):
        """Extract price information from HTML content"""
        pass 