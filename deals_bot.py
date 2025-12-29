import logging
import asyncio
import os
import sys
from datetime import datetime, time as dt_time
from typing import Optional
import argparse
from dotenv import load_dotenv

from google_sheets import GoogleSheetsReader
from deals_checker import DealsChecker
from deals_tracker import DealsTracker
from telegram_notifier import TelegramNotifier

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

MIN_DISCOUNT_PERCENT = float(os.getenv('MIN_DISCOUNT_PERCENT', '10'))
MAX_DEALS_PER_RUN = int(os.getenv('MAX_DEALS_PER_RUN', '10'))
DUPLICATE_CHECK_HOURS = int(os.getenv('DUPLICATE_CHECK_HOURS', '24'))
MESSAGE_DELAY_SECONDS = float(os.getenv('MESSAGE_DELAY_SECONDS', '3'))

DB_PATH = os.getenv('DEALS_DB_PATH', 'deals_history.db')

DEFAULT_SHEET_GIDS = {
    "EARPHONES": 841822689,      
    # "HEADPHONES": 362895356,     
    "ELETRÔNICOS": 1891840859,   
}


class DealsBot:
    
    def __init__(
        self,
        spreadsheet_id: str = None,
        sheet_gids: dict = None,
        min_discount: float = None,
        db_path: str = None
    ):
        
        self.spreadsheet_id = spreadsheet_id or SPREADSHEET_ID
        self.sheet_gids = sheet_gids or DEFAULT_SHEET_GIDS
        self.min_discount = min_discount or MIN_DISCOUNT_PERCENT
        self.db_path = db_path or DB_PATH
        
        if not self.spreadsheet_id:
            raise ValueError("GOOGLE_SPREADSHEET_ID is required")
        
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if not TELEGRAM_CHANNEL_ID:
            raise ValueError("TELEGRAM_CHANNEL_ID is required")
        
        self.sheets_reader = GoogleSheetsReader(self.spreadsheet_id)
        self.tracker = DealsTracker(self.db_path)
        self.checker = DealsChecker(min_discount_percent=self.min_discount)
        self.notifier = TelegramNotifier(tracker=self.tracker)
        
        logger.info(f"DealsBot initialized")
        logger.info(f"  Spreadsheet: {self.spreadsheet_id}")
        logger.info(f"  Channel: {TELEGRAM_CHANNEL_ID}")
        logger.info(f"  Min discount: {self.min_discount}%")
        logger.info(f"  Database: {self.db_path}")
    
    async def run_check(
        self,
        send_deals: bool = True,
        max_deals: int = None
    ) -> dict:
        logger.info("=" * 50)
        logger.info("Starting deals check...")
        start_time = datetime.now()
        
        results = {
            "timestamp": start_time.isoformat(),
            "products_checked": 0,
            "deals_found": 0,
            "deals_sent": 0,
            "errors": []
        }
        
        try:
            logger.info("Fetching products from Google Sheets...")
            products = self.sheets_reader.get_products_with_aliexpress_links(self.sheet_gids)
            results["products_checked"] = len(products)
            
            if not products:
                logger.warning("No products found in spreadsheet")
                return results
            
            logger.info(f"Found {len(products)} products with AliExpress links")
            
            logger.info("Checking prices on AliExpress...")
            deals = await self.checker.check_all_products(
                products,
                tracker=self.tracker,
                skip_recent=True,
                recent_hours=DUPLICATE_CHECK_HOURS
            )
            
            results["deals_found"] = len(deals)
            
            if not deals:
                logger.info("No new deals found")
                return results
            
            logger.info(f"Found {len(deals)} deals!")
            
            max_to_send = max_deals or MAX_DEALS_PER_RUN
            best_deals = self.checker.filter_best_deals(deals, max_deals=max_to_send)
            
            if send_deals and best_deals:
                logger.info(f"Sending {len(best_deals)} deals to Telegram...")
                message_ids = await self.notifier.send_deals_batch(
                    best_deals,
                    delay_seconds=MESSAGE_DELAY_SECONDS,
                    max_deals=max_to_send
                )
                results["deals_sent"] = len(message_ids)
            else:
                logger.info("Deals sending disabled or no deals to send")
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Check completed in {duration:.1f}s")
            logger.info(f"  Products checked: {results['products_checked']}")
            logger.info(f"  Deals found: {results['deals_found']}")
            logger.info(f"  Deals sent: {results['deals_sent']}")
            
            return results
            
        except Exception as e:
            logger.exception(f"Error during deals check: {e}")
            results["errors"].append(str(e))
            return results
    
    async def send_active_deals_summary(self) -> bool:
        logger.info("Sending active deals summary...")
        
        try:
            active_deals = self.tracker.get_active_deals(hours=48)
            
            if not active_deals:
                logger.info("No active deals for summary")
                return False
            
            message_id = await self.notifier.send_summary(active_deals)
            
            if message_id:
                logger.info(f"Summary sent successfully (message ID: {message_id})")
                return True
            else:
                logger.error("Failed to send summary")
                return False
                
        except Exception as e:
            logger.exception(f"Error sending summary: {e}")
            return False
    
    async def send_daily_digest(self) -> bool:
        logger.info("Sending daily digest...")
        
        try:
            message_id = await self.notifier.send_daily_digest()
            return message_id is not None
        except Exception as e:
            logger.exception(f"Error sending daily digest: {e}")
            return False
    
    def cleanup_database(self, days: int = 90):
        logger.info(f"Cleaning up records older than {days} days...")
        self.tracker.cleanup_old_records(days)
    
    async def run_continuous(
        self,
        check_interval_hours: float = 6,
        summary_times: list = None
    ):
        logger.info(f"Starting continuous mode (check every {check_interval_hours}h)")
        
        if summary_times is None:
            summary_times = ["10:00", "18:00"]  
        
        check_interval_seconds = check_interval_hours * 3600
        last_summary_date = {}
        
        while True:
            try:
                await self.run_check()
                
                current_time = datetime.now()
                current_time_str = current_time.strftime("%H:%M")
                current_date = current_time.date()
                
                for summary_time in summary_times:
                    if abs(self._time_diff_minutes(current_time_str, summary_time)) <= 5:
                        if last_summary_date.get(summary_time) != current_date:
                            await self.send_active_deals_summary()
                            last_summary_date[summary_time] = current_date
                
                logger.info(f"Next check in {check_interval_hours} hours...")
                await asyncio.sleep(check_interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.exception(f"Error in continuous loop: {e}")
                await asyncio.sleep(300)  
    
    def _time_diff_minutes(self, time1: str, time2: str) -> int:
        h1, m1 = map(int, time1.split(":"))
        h2, m2 = map(int, time2.split(":"))
        return abs((h1 * 60 + m1) - (h2 * 60 + m2))


async def main():
    parser = argparse.ArgumentParser(
        description="AliExpress Deals Bot - Monitor deals and post to Telegram"
    )
    
    parser.add_argument(
        "--mode",
        choices=["check", "summary", "digest", "continuous", "test"],
        default="check",
        help="Operating mode"
    )
    
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Check for deals but don't send to Telegram"
    )
    
    parser.add_argument(
        "--max-deals",
        type=int,
        default=None,
        help="Maximum deals to send"
    )
    
    parser.add_argument(
        "--interval",
        type=float,
        default=6,
        help="Check interval in hours (for continuous mode)"
    )
    
    parser.add_argument(
        "--cleanup-days",
        type=int,
        default=90,
        help="Clean up records older than N days"
    )
    
    args = parser.parse_args()
    
    missing_vars = []
    for var in ['GOOGLE_SPREADSHEET_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID', 
                'ALIEXPRESS_APP_KEY', 'ALIEXPRESS_APP_SECRET']:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars and args.mode != "test":
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file")
        sys.exit(1)
    
    try:
        bot = DealsBot()
        
        if args.mode == "check":
            results = await bot.run_check(
                send_deals=not args.no_send,
                max_deals=args.max_deals
            )
            print(f"\nResults: {results}")
            
        elif args.mode == "summary":
            success = await bot.send_active_deals_summary()
            sys.exit(0 if success else 1)
            
        elif args.mode == "digest":
            success = await bot.send_daily_digest()
            sys.exit(0 if success else 1)
            
        elif args.mode == "continuous":
            await bot.run_continuous(check_interval_hours=args.interval)
            
        elif args.mode == "test":
            logger.info("Running in test mode...")
            
            connected = await bot.notifier.test_connection()
            print(f"Telegram connection: {'✓' if connected else '✗'}")
            
            try:
                products = bot.sheets_reader.get_products_with_aliexpress_links(bot.sheet_gids)
                print(f"Google Sheets: ✓ ({len(products)} products found)")
            except Exception as e:
                print(f"Google Sheets: ✗ ({e})")
            
            try:
                summary = bot.tracker.get_deals_summary()
                print(f"Database: ✓ (history: {summary['total_deals']} deals in 24h)")
            except Exception as e:
                print(f"Database: ✗ ({e})")
        
        if args.cleanup_days > 0:
            bot.cleanup_database(args.cleanup_days)
            
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

