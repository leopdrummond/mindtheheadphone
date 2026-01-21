import os
import sys
import json
from dotenv import load_dotenv
import iop

load_dotenv()

def test_product(product_id: str):
    """Test fetching a specific product with different configurations."""
    
    app_key = os.getenv('ALIEXPRESS_APP_KEY')
    app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
    tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', 'default')
    
    if not app_key or not app_secret:
        print("❌ Error: ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET must be set in .env")
        return
    
    client = iop.IopClient(
        'https://api-sg.aliexpress.com/sync',
        app_key,
        app_secret
    )
    
    print(f"\n{'='*60}")
    print(f"Testing Product ID: {product_id}")
    print(f"{'='*60}\n")
    
    # Test configurations
    test_configs = [
        ("BRL, no country", 'BRL', None),
        ("USD, no country", 'USD', None),
        ("BRL, country=BR", 'BRL', 'BR'),
        ("USD, country=BR", 'USD', 'BR'),
    ]
    
    for config_name, currency, country in test_configs:
        print(f"\n{'─'*60}")
        print(f"Test: {config_name}")
        print(f"{'─'*60}")
        
        try:
            request = iop.IopRequest('aliexpress.affiliate.productdetail.get')
            request.add_api_param('fields', 'product_main_image_url,target_sale_price,product_title,target_sale_price_currency,target_original_price,target_original_price_currency,product_id,product_url')
            request.add_api_param('product_ids', product_id)
            request.add_api_param('target_currency', currency)
            request.add_api_param('target_language', 'en')
            request.add_api_param('tracking_id', tracking_id)
            
            if country:
                request.add_api_param('country', country)
            
            print(f"Request params: currency={currency}, country={country or 'None'}")
            response = client.execute(request)
            
            print(f"Response code: {response.code}")
            print(f"Response type: {response.type}")
            print(f"Response message: {response.message}")
            
            if response.body:
                if 'error_response' in response.body:
                    error = response.body['error_response']
                    print(f"❌ API ERROR:")
                    print(f"   Code: {error.get('code')}")
                    print(f"   Message: {error.get('msg')}")
                else:
                    detail_response = response.body.get('aliexpress_affiliate_productdetail_get_response', {})
                    resp_result = detail_response.get('resp_result', {})
                    
                    print(f"Response code: {resp_result.get('resp_code')}")
                    
                    if resp_result.get('resp_code') == 200:
                        result = resp_result.get('result', {})
                        products_data = result.get('products', {})
                        
                        print(f"   Products data type: {type(products_data)}")
                        print(f"   Products data: {products_data}")
                        
                        # Check different possible structures
                        products = None
                        if isinstance(products_data, dict):
                            products = products_data.get('product', [])
                            if not products and 'product' in products_data:
                                # Might be a single product dict, not a list
                                if isinstance(products_data.get('product'), dict):
                                    products = [products_data.get('product')]
                        elif isinstance(products_data, list):
                            products = products_data
                        
                        print(f"   Extracted products: {products}")
                        print(f"   Products type: {type(products)}")
                        print(f"   Products length: {len(products) if products else 0}")
                        
                        if products and len(products) > 0:
                            product = products[0] if isinstance(products, list) else products
                            print(f"✅ SUCCESS!")
                            print(f"   Title: {product.get('product_title', 'N/A')}")
                            print(f"   Sale Price: {product.get('target_sale_price', 'N/A')} {product.get('target_sale_price_currency', 'N/A')}")
                            print(f"   Original Price: {product.get('target_original_price', 'N/A')} {product.get('target_original_price_currency', 'N/A')}")
                            print(f"   Product ID: {product.get('product_id', 'N/A')}")
                        else:
                            print(f"⚠️  No products in response")
                            print(f"   Result keys: {list(result.keys())}")
                            print(f"   Full result structure:")
                            print(json.dumps(result, indent=2, default=str))
                            if 'error_desc' in resp_result:
                                print(f"   Error description: {resp_result.get('error_desc')}")
                    else:
                        print(f"❌ Response code not 200: {resp_result.get('resp_code')}")
                        if 'error_desc' in resp_result:
                            print(f"   Error description: {resp_result.get('error_desc')}")
            else:
                print("❌ Empty response body")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("Test completed")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        product_id = sys.argv[1]
    else:
        # Default test product ID (you can change this)
        product_id = "1005006318149817"  # Moondrop May from the logs
    
    test_product(product_id)

