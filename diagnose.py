import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def check_env():
    print("=" * 60)
    print("ENVIRONMENT VARIABLES CHECK")
    print("=" * 60)
    
    required = {
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHANNEL_ID': os.getenv('TELEGRAM_CHANNEL_ID'),
        'GOOGLE_SPREADSHEET_ID': os.getenv('GOOGLE_SPREADSHEET_ID'),
        'ALIEXPRESS_APP_KEY': os.getenv('ALIEXPRESS_APP_KEY'),
        'ALIEXPRESS_APP_SECRET': os.getenv('ALIEXPRESS_APP_SECRET'),
        'ALIEXPRESS_TRACKING_ID': os.getenv('ALIEXPRESS_TRACKING_ID'),
    }
    
    for key, value in required.items():
        if value:
            if 'SECRET' in key or 'TOKEN' in key:
                display = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display = value
            print(f"✅ {key}: {display}")
        else:
            print(f"❌ {key}: NOT SET")
    
    print()

def check_telegram():
    print("=" * 60)
    print("TELEGRAM BOT CHECK")
    print("=" * 60)
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return
    
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                print(f"✅ Bot connected: @{bot_info.get('username')}")
                print(f"   Bot name: {bot_info.get('first_name')}")
            else:
                print(f"❌ Bot API error: {data.get('description')}")
        else:
            print(f"❌ HTTP error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    if channel_id:
        try:
            url = f"https://api.telegram.org/bot{token}/getChat"
            response = requests.post(url, json={'chat_id': channel_id}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    chat_info = data.get('result', {})
                    print(f"✅ Channel accessible: {chat_info.get('title', channel_id)}")
                else:
                    print(f"❌ Cannot access channel: {data.get('description')}")
                    print(f"   Make sure:")
                    print(f"   1. Channel exists: {channel_id}")
                    print(f"   2. Bot is added as admin")
                    print(f"   3. Bot has 'Post Messages' permission")
            else:
                print(f"❌ HTTP error checking channel: {response.status_code}")
        except Exception as e:
            print(f"❌ Error checking channel: {e}")
    else:
        print("⚠️  TELEGRAM_CHANNEL_ID not set")
    
    print()

def check_google_sheets():
    print("=" * 60)
    print("GOOGLE SHEETS CHECK")
    print("=" * 60)
    
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    
    if not spreadsheet_id:
        print("❌ GOOGLE_SPREADSHEET_ID not set")
        return
    
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Spreadsheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    print()
    
    test_gids = [0, 841822689]
    
    for gid in test_gids:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                content = response.text[:100]
                if content.startswith('<!DOCTYPE') or content.startswith('<html'):
                    print(f"❌ GID {gid}: Got HTML (404 or access denied)")
                    print(f"   → Spreadsheet may not be publicly shared")
                else:
                    lines = len(response.text.split('\n'))
                    print(f"✅ GID {gid}: Accessible ({lines} lines)")
            else:
                print(f"❌ GID {gid}: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ GID {gid}: Error - {e}")
    
    print()
    print("💡 TIP: Make sure your spreadsheet is:")
    print("   1. Shared publicly (Anyone with the link can view)")
    print("   2. Not restricted by domain")
    print("   3. GIDs match the actual sheet tabs")

def main():
    print("\n🔍 DIAGNOSTIC CHECK\n")
    
    check_env()
    check_telegram()
    check_google_sheets()
    
    print("=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()

