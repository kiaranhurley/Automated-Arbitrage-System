import json
import re
from urllib.parse import urljoin

from app.marketplace.marketplace_scraper import MarketplaceScraper
from config import STEAM_API_KEY


class SteamScraper(MarketplaceScraper):
    def __init__(self, marketplace_id):
        super().__init__(
            marketplace_id=marketplace_id,
            name="Steam",
            base_url="https://store.steampowered.com"
        )
        self.api_key = STEAM_API_KEY
        
    def search_products(self, query):
        """Search for products on Steam"""
        search_url = f"{self.base_url}/search/results"
        params = {
            'term': query,
            'category1': 998,  # Games category
            'json': 1
        }
        
        try:
            response = self._make_request(search_url, headers={'X-Requested-With': 'XMLHttpRequest'})
            data = response.json()
            
            products = []
            for item in data.get('results', []):
                product_data = {
                    'name': item.get('name'),
                    'identifier': str(item.get('id')),
                    'url': f"{self.base_url}/app/{item.get('id')}",
                    'metadata': {
                        'steam_id': item.get('id'),
                        'type': item.get('type'),
                        'released': item.get('released')
                    }
                }
                
                if self.validate_product_data(product_data):
                    products.append(product_data)
            
            return products
        except Exception as e:
            self.logger.error(f"Failed to search Steam products: {str(e)}")
            return []

    def get_product_details(self, product_url):
        """Get detailed information about a Steam product"""
        try:
            app_id = self._extract_app_id(product_url)
            if not app_id:
                return None

            # Use Steam Store API
            api_url = f"{self.base_url}/api/appdetails"
            params = {'appids': app_id}
            
            response = self._make_request(api_url)
            data = response.json()
            
            if not data[app_id]['success']:
                return None
                
            details = data[app_id]['data']
            
            return {
                'name': details.get('name'),
                'identifier': str(app_id),
                'description': details.get('short_description'),
                'category': details.get('type'),
                'metadata': {
                    'steam_id': app_id,
                    'developers': details.get('developers', []),
                    'publishers': details.get('publishers', []),
                    'release_date': details.get('release_date', {}).get('date'),
                    'categories': [cat.get('description') for cat in details.get('categories', [])],
                    'genres': [genre.get('description') for genre in details.get('genres', [])]
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get Steam product details: {str(e)}")
            return None

    def get_price(self, product_url, region='US'):
        """Get the current price for a Steam product"""
        try:
            app_id = self._extract_app_id(product_url)
            if not app_id:
                return None

            # Use Steam Store API for prices
            api_url = f"{self.base_url}/api/appdetails"
            params = {
                'appids': app_id,
                'cc': region,
                'filters': 'price_overview'
            }
            
            response = self._make_request(api_url, params=params)
            data = response.json()
            
            if not data[app_id]['success']:
                return None
                
            price_data = data[app_id]['data'].get('price_overview', {})
            
            if not price_data:
                return None
                
            return {
                'price': price_data.get('final') / 100,  # Convert to decimal
                'currency': price_data.get('currency'),
                'initial_price': price_data.get('initial') / 100,
                'discount_percent': price_data.get('discount_percent', 0)
            }
        except Exception as e:
            self.logger.error(f"Failed to get Steam price: {str(e)}")
            return None

    def extract_product_info(self, html):
        """Extract product information from Steam HTML content"""
        soup = self._parse_html(html)
        
        # Extract basic information
        name = soup.find('div', class_='apphub_AppName')
        description = soup.find('div', class_='game_description_snippet')
        
        if not name:
            return None
            
        return {
            'name': name.text.strip(),
            'description': description.text.strip() if description else None,
        }

    def extract_price_info(self, html):
        """Extract price information from Steam HTML content"""
        soup = self._parse_html(html)
        
        price_element = soup.find('div', class_='game_purchase_price') or \
                       soup.find('div', class_='discount_final_price')
                       
        if not price_element:
            return None
            
        price_text = price_element.text.strip()
        price = self._clean_price(price_text)
        
        return {
            'price': price,
            'currency': self._extract_currency(price_text)
        }

    def _extract_app_id(self, url):
        """Extract Steam App ID from URL"""
        match = re.search(r'/app/(\d+)', url)
        return match.group(1) if match else None

    def _extract_currency(self, price_text):
        """Extract currency from price text"""
        currency_map = {
            '$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            'A$': 'AUD',
            'CA$': 'CAD'
        }
        
        for symbol, code in currency_map.items():
            if symbol in price_text:
                return code
        return 'USD'  # Default currency 