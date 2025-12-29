import logging
import asyncio
import aiohttp
import re
import os
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv

import iop
from google_sheets import Product, GoogleSheetsReader
from deals_tracker import DealsTracker

load_dotenv()

logger = logging.getLogger(__name__)

ALIEXPRESS_API_URL = os.getenv('ALIEXPRESS_API_URL', 'https://api-sg.aliexpress.com/sync')
ALIEXPRESS_APP_KEY = os.getenv('ALIEXPRESS_APP_KEY')
ALIEXPRESS_APP_SECRET = os.getenv('ALIEXPRESS_APP_SECRET')
ALIEXPRESS_TRACKING_ID = os.getenv('ALIEXPRESS_TRACKING_ID', 'default')
TARGET_CURRENCY = os.getenv('TARGET_CURRENCY', 'BRL')  # Changed to BRL for Brazilian market
TARGET_LANGUAGE = os.getenv('TARGET_LANGUAGE', 'en')
QUERY_COUNTRY = os.getenv('QUERY_COUNTRY', 'BR')  # Changed to BR for Brazil


@dataclass
class Deal:
    product: Product
    current_price: float
    original_price: float
    discount_percent: float
    discount_amount: float
    currency: str
    affiliate_link: str
    product_id: str
    image_url: Optional[str] = None
    title: Optional[str] = None
    checked_at: datetime = None
    
    def __post_init__(self):
        if self.checked_at is None:
            self.checked_at = datetime.now()
    
    @property
    def is_significant_deal(self) -> bool:
        return self.discount_percent >= 10.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product.name,
            "category": self.product.category,
            "section": self.product.section,
            "current_price": self.current_price,
            "original_price": self.original_price,
            "discount_percent": self.discount_percent,
            "discount_amount": self.discount_amount,
            "currency": self.currency,
            "affiliate_link": self.affiliate_link,
            "product_id": self.product_id,
            "image_url": self.image_url,
            "checked_at": self.checked_at.isoformat()
        }


class DealsChecker:
    
    PRODUCT_ID_REGEX = re.compile(r'/item/(\d+)\.html')
    SHORT_LINK_REGEX = re.compile(
        r'https?://(?:s\.click\.aliexpress\.com/e/|a\.aliexpress\.com/_)[a-zA-Z0-9_-]+/?',
        re.IGNORECASE
    )
    
    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        tracking_id: str = None,
        min_discount_percent: float = 10.0,
        currency: str = None,
        country: str = None
    ):
        self.app_key = app_key or ALIEXPRESS_APP_KEY
        self.app_secret = app_secret or ALIEXPRESS_APP_SECRET
        self.tracking_id = tracking_id or ALIEXPRESS_TRACKING_ID
        self.min_discount_percent = min_discount_percent
        self.currency = currency or TARGET_CURRENCY
        self.country = country or QUERY_COUNTRY
        
        if self.app_key and self.app_secret:
            self.api_client = iop.IopClient(
                ALIEXPRESS_API_URL, 
                self.app_key, 
                self.app_secret
            )
            logger.info("AliExpress API client initialized")
        else:
            self.api_client = None
            logger.warning("AliExpress API credentials not provided")
    
    async def resolve_short_link(
        self, 
        short_url: str, 
        session: aiohttp.ClientSession
    ) -> Optional[str]:
        logger.debug(f"Resolving short link: {short_url}")
        
        try:
            async with session.get(
                short_url, 
                allow_redirects=True, 
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200 and response.url:
                    final_url = str(response.url)
                    
                    if '.aliexpress.us' in final_url:
                        final_url = final_url.replace('.aliexpress.us', '.aliexpress.com')
                    
                    logger.debug(f"Resolved {short_url} -> {final_url}")
                    return final_url
                else:
                    logger.warning(f"Failed to resolve {short_url}: status {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout resolving {short_url}")
            return None
        except Exception as e:
            logger.error(f"Error resolving {short_url}: {e}")
            return None
    
    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID from an AliExpress URL."""
        if not url:
            return None
            
        if '.aliexpress.us' in url:
            url = url.replace('.aliexpress.us', '.aliexpress.com')
        
        match = self.PRODUCT_ID_REGEX.search(url)
        if match:
            return match.group(1)
        
        alt_patterns = [
            r'/p/[^/]+/([0-9]+)\.html',
            r'product/([0-9]+)',
            r'productId=(\d+)',
        ]
        
        for pattern in alt_patterns:
            alt_match = re.search(pattern, url)
            if alt_match:
                return alt_match.group(1)
        
        return None
    
    def _fetch_product_details_sync(self, product_id: str) -> Optional[Dict[str, Any]]:
        if not self.api_client:
            logger.error("API client not initialized")
            return None
        
        try:
            request = iop.IopRequest('aliexpress.affiliate.productdetail.get')
            request.add_api_param('fields', 'product_main_image_url,target_sale_price,product_title,target_sale_price_currency,target_original_price,target_original_price_currency')
            request.add_api_param('product_ids', product_id)
            request.add_api_param('target_currency', self.currency)
            request.add_api_param('target_language', TARGET_LANGUAGE)
            request.add_api_param('tracking_id', self.tracking_id)
            request.add_api_param('country', self.country)
            
            response = self.api_client.execute(request)
            
            if not response or not response.body:
                logger.error(f"Empty response for product {product_id}")
                return None
            
            response_data = response.body
            
            if 'error_response' in response_data:
                error = response_data['error_response']
                error_msg = error.get('msg', 'Unknown')
                error_code = error.get('code', 'Unknown')
                
                if 'ApiCallLimit' in error_code or 'frequency' in error_msg.lower():
                    logger.warning(f"Rate limited for {product_id}, will retry later")
                    return None
                
                logger.error(f"API error for {product_id}: Code={error_code}, Msg={error_msg}")
                
                if 'signature' in error_msg.lower() or error_code in ['400', '401']:
                    logger.warning("API signature error detected. Your app might be in 'Test' status and needs approval.")
                    logger.warning("Check your AliExpress Affiliate Portal to ensure the app is approved for production use.")
                
                return None
            
            detail_response = response_data.get('aliexpress_affiliate_productdetail_get_response', {})
            resp_result = detail_response.get('resp_result', {})
            
            if resp_result.get('resp_code') != 200:
                logger.error(f"API response code not 200 for {product_id}")
                return None
            
            result = resp_result.get('result', {})
            products = result.get('products', {}).get('product', [])
            
            if not products:
                logger.warning(f"No products found for {product_id}")
                return None
            
            product_data = products[0]
            
            return {
                'product_id': product_id,
                'title': product_data.get('product_title'),
                'image_url': product_data.get('product_main_image_url'),
                'sale_price': float(product_data.get('target_sale_price', 0) or 0),
                'original_price': float(product_data.get('target_original_price', 0) or 0),
                'currency': product_data.get('target_sale_price_currency', self.currency),
            }
            
        except Exception as e:
            logger.exception(f"Error fetching product {product_id}: {e}")
            return None
    
    async def fetch_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_product_details_sync, product_id)
    
    def _generate_affiliate_link_sync(self, target_url: str) -> Optional[str]:
        if not self.api_client:
            logger.error("API client not initialized")
            return None
        
        try:
            if "star.aliexpress.com" not in target_url:
                source_url = f"https://star.aliexpress.com/share/share.htm?&redirectUrl={target_url}"
            else:
                source_url = target_url
            
            request = iop.IopRequest('aliexpress.affiliate.link.generate')
            request.add_api_param('promotion_link_type', '0')
            request.add_api_param('source_values', source_url)
            request.add_api_param('tracking_id', self.tracking_id)
            
            response = self.api_client.execute(request)
            
            if not response or not response.body:
                return None
            
            response_data = response.body
            
            if 'error_response' in response_data:
                logger.error(f"Link generation error: {response_data['error_response']}")
                return None
            
            generate_response = response_data.get('aliexpress_affiliate_link_generate_response', {})
            resp_result = generate_response.get('resp_result', {})
            
            if resp_result.get('resp_code') != 200:
                return None
            
            links = resp_result.get('result', {}).get('promotion_links', {}).get('promotion_link', [])
            
            if links and len(links) > 0:
                return links[0].get('promotion_link')
            
            return None
            
        except Exception as e:
            logger.exception(f"Error generating affiliate link: {e}")
            return None
    
    async def generate_affiliate_link(self, target_url: str) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_affiliate_link_sync, target_url)
    
    async def check_product_for_deal(
        self,
        product: Product,
        session: aiohttp.ClientSession
    ) -> Optional[Deal]:
        try:
            product_id = None
            resolved_url = None
            
            if self.SHORT_LINK_REGEX.match(product.aliexpress_link):
                resolved_url = await self.resolve_short_link(product.aliexpress_link, session)
                if resolved_url:
                    product_id = self.extract_product_id(resolved_url)
            else:
                product_id = self.extract_product_id(product.aliexpress_link)
                resolved_url = product.aliexpress_link
            
            if not product_id:
                logger.warning(f"Could not extract product ID for {product.name}")
                return None
            
            # Validate product ID (should be a long numeric string, not "404" or other invalid values)
            if not product_id.isdigit() or len(product_id) < 10:
                logger.warning(f"Invalid product ID '{product_id}' for {product.name} (too short or not numeric)")
                return None
            
            details = await self.fetch_product_details(product_id)
            
            if not details:
                logger.warning(f"Could not fetch details for {product.name} (ID: {product_id})")
                return None
            
            current_price = details['sale_price']
            
            if current_price <= 0:
                logger.warning(f"Invalid price for {product.name}: {current_price}")
                return None
            
            # Use final_price as reference, fallback to base_price if final_price is missing
            reference_price_brl = product.final_price if product.final_price > 0 else product.base_price
            
            if reference_price_brl <= 0:
                logger.warning(f"No reference price (final_price or base_price) for {product.name}")
                return None
            
            from brazil_taxes import calculate_final_price_brl, get_exchange_rate
            
            exchange_rate = get_exchange_rate()
            
            if details['currency'].upper() == 'BRL':
                current_price_usd = current_price / exchange_rate
            else:
                current_price_usd = current_price
            
            current_final_brl, _, _ = calculate_final_price_brl(current_price_usd, exchange_rate)
            
            if current_final_brl >= reference_price_brl:
                logger.debug(f"{product.name}: Current price R${current_final_brl:.2f} >= Reference R${reference_price_brl:.2f}")
                return None
            
            discount_amount_brl = reference_price_brl - current_final_brl
            discount_percent = (discount_amount_brl / reference_price_brl) * 100
            
            if discount_percent < self.min_discount_percent:
                logger.debug(f"{product.name}: {discount_percent:.1f}% discount (below {self.min_discount_percent}%)")
                return None
            
            original_price_brl = reference_price_brl
            
            affiliate_link = await self.generate_affiliate_link(
                f"https://www.aliexpress.com/item/{product_id}.html"
            )
            
            if not affiliate_link or not affiliate_link.startswith('http'):
                affiliate_link = product.aliexpress_link
                
            if not affiliate_link or affiliate_link == '-' or not affiliate_link.startswith('http'):
                logger.warning(f"Invalid affiliate link for {product.name}, skipping deal")
                return None
            
            deal = Deal(
                product=product,
                current_price=current_price,
                original_price=original_price_brl,
                discount_percent=discount_percent,
                discount_amount=discount_amount_brl,
                currency='BRL',
                affiliate_link=affiliate_link,
                product_id=product_id,
                image_url=details.get('image_url'),
                title=details.get('title') or product.name
            )
            
            logger.info(
                f"Found deal: {product.name} - {discount_percent:.1f}% off "
                f"(R$ {original_price_brl:.2f} -> R$ {current_final_brl:.2f} with taxes)"
            )
            
            return deal
            
        except Exception as e:
            logger.exception(f"Error checking product {product.name}: {e}")
            return None
    
    async def check_all_products(
        self,
        products: List[Product],
        tracker: DealsTracker = None,
        skip_recent: bool = True,
        recent_hours: int = 24
    ) -> List[Deal]:
        deals = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            products_to_check = []
            
            for product in products:
                if not product.aliexpress_link:
                    continue
                
                if skip_recent and tracker:
                    if tracker.was_deal_sent_recently(product.aliexpress_link, hours=recent_hours):
                        logger.debug(f"Skipping {product.name} - recently sent")
                        continue
                
                products_to_check.append(product)
                tasks.append(self.check_product_for_deal(product, session))
            
            logger.info(f"Checking {len(tasks)} products for deals...")
            
            batch_size = 5  
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                results = await asyncio.gather(*batch, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Error in batch: {result}")
                    elif result is not None:
                        deals.append(result)
                
                if i + batch_size < len(tasks):
                    await asyncio.sleep(2)  
        
        logger.info(f"Found {len(deals)} deals out of {len(products)} products")
        return deals
    
    def filter_best_deals(
        self,
        deals: List[Deal],
        max_deals: int = 10,
        min_discount: float = None
    ) -> List[Deal]:
        min_discount = min_discount or self.min_discount_percent
        
        filtered = [d for d in deals if d.discount_percent >= min_discount]
        
        filtered.sort(key=lambda d: d.discount_percent, reverse=True)
        
        return filtered[:max_deals]


async def main():
    logging.basicConfig(level=logging.INFO)
    
    checker = DealsChecker(min_discount_percent=10.0)
    
    from google_sheets import Product
    
    test_product = Product(
        name="Test Earphone",
        category="EARPHONES",
        section="in-ears",
        base_price=100.0,
        final_price=145.0,
        tax_rate=45.0,
        aliexpress_link="https://s.click.aliexpress.com/e/_c30WJKMz"  # Example link
    )
    
    async with aiohttp.ClientSession() as session:
        deal = await checker.check_product_for_deal(test_product, session)
        
        if deal:
            print(f"\nDeal found!")
            print(f"  Product: {deal.title}")
            print(f"  Price: {deal.currency} {deal.original_price:.2f} -> {deal.current_price:.2f}")
            print(f"  Discount: {deal.discount_percent:.1f}%")
            print(f"  Link: {deal.affiliate_link}")
        else:
            print("No deal found for test product")


if __name__ == "__main__":
    asyncio.run(main())

