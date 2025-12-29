import os
import sys
from dotenv import load_dotenv
import iop

load_dotenv()

def test_api():
    app_key = os.getenv('ALIEXPRESS_APP_KEY')
    app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
    tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', 'default')
    api_url = os.getenv('ALIEXPRESS_API_URL', 'https://api-sg.aliexpress.com/sync')
    
    print("=" * 60)
    print("ALIEXPRESS API TEST")
    print("=" * 60)
    print(f"API URL: {api_url}")
    print(f"App Key: {app_key}")
    print(f"Tracking ID: {tracking_id}")
    print()
    
    if not app_key or not app_secret:
        print("❌ Missing API credentials in .env")
        return
    
    client = iop.IopClient(api_url, app_key, app_secret)
    
    test_product_id = "1005007431129955"
    
    print(f"Testing with product ID: {test_product_id}")
    print()
    
    try:
        request = iop.IopRequest('aliexpress.affiliate.productdetail.get')
        request.add_api_param('fields', 'product_main_image_url,target_sale_price,product_title')
        request.add_api_param('product_ids', test_product_id)
        request.add_api_param('target_currency', 'USD')
        request.add_api_param('target_language', 'en')
        request.add_api_param('tracking_id', tracking_id)
        request.add_api_param('country', 'US')
        
        print("Sending API request...")
        response = client.execute(request)
        
        print(f"Response code: {response.code}")
        print(f"Response type: {response.type}")
        print(f"Response message: {response.message}")
        print()
        
        if response.body:
            if 'error_response' in response.body:
                error = response.body['error_response']
                print("❌ API ERROR:")
                print(f"   Code: {error.get('code')}")
                print(f"   Message: {error.get('msg')}")
                print(f"   Request ID: {error.get('request_id')}")
                print()
                print("💡 Possible solutions:")
                print("   1. Check if your app is approved (not in Test status)")
                print("   2. Verify API credentials are correct")
                print("   3. Check AliExpress API documentation for changes")
            else:
                print("✅ API call successful!")
                print(f"Response: {response.body}")
        else:
            print("❌ Empty response body")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()

