import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class SentDeal:
    id: int
    product_name: str
    product_link: str
    original_price: float
    deal_price: float
    discount_percent: float
    affiliate_link: str
    sent_at: datetime
    telegram_message_id: Optional[int]
    is_active: bool
    category: str
    section: str
    
    @property
    def age_hours(self) -> float:
        return (datetime.now() - self.sent_at).total_seconds() / 3600


class DealsTracker:
    
    def __init__(self, db_path: str = "deals_history.db"):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sent_deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    product_link TEXT NOT NULL,
                    original_price REAL NOT NULL,
                    deal_price REAL NOT NULL,
                    discount_percent REAL NOT NULL,
                    affiliate_link TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    category TEXT,
                    section TEXT,
                    product_id TEXT,
                    extra_data TEXT
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_product_link 
                ON sent_deals(product_link)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sent_at 
                ON sent_deals(sent_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_active 
                ON sent_deals(is_active)
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_link TEXT NOT NULL,
                    price REAL NOT NULL,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def was_deal_sent_recently(
        self, 
        product_link: str, 
        hours: int = 24,
        price_threshold: float = 0.05
    ) -> bool:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM sent_deals 
                WHERE product_link = ? AND sent_at > ?
                ORDER BY sent_at DESC
                LIMIT 1
            """, (product_link, cutoff))
            
            row = cursor.fetchone()
            
            if row:
                logger.debug(f"Found recent deal for {product_link} sent at {row['sent_at']}")
                return True
            
            return False
    
    def was_same_price_sent(
        self, 
        product_link: str, 
        current_price: float,
        hours: int = 48,
        tolerance: float = 0.02
    ) -> bool:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT deal_price FROM sent_deals 
                WHERE product_link = ? AND sent_at > ?
                ORDER BY sent_at DESC
            """, (product_link, cutoff))
            
            for row in cursor.fetchall():
                prev_price = row['deal_price']
                diff_ratio = abs(prev_price - current_price) / prev_price if prev_price > 0 else 1
                
                if diff_ratio <= tolerance:
                    logger.debug(f"Same price deal already sent: {prev_price} vs {current_price}")
                    return True
            
            return False
    
    def record_sent_deal(
        self,
        product_name: str,
        product_link: str,
        original_price: float,
        deal_price: float,
        discount_percent: float,
        affiliate_link: str,
        telegram_message_id: Optional[int] = None,
        category: str = "",
        section: str = "",
        product_id: str = "",
        extra_data: Dict[str, Any] = None
    ) -> int:

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sent_deals 
                (product_name, product_link, original_price, deal_price, 
                 discount_percent, affiliate_link, telegram_message_id,
                 category, section, product_id, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_name, product_link, original_price, deal_price,
                discount_percent, affiliate_link, telegram_message_id,
                category, section, product_id,
                json.dumps(extra_data) if extra_data else None
            ))
            
            conn.commit()
            deal_id = cursor.lastrowid
            
            logger.info(f"Recorded deal #{deal_id}: {product_name} at R${deal_price:.2f} ({discount_percent:.1f}% off)")
            return deal_id
    
    def update_message_id(self, deal_id: int, telegram_message_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sent_deals 
                SET telegram_message_id = ?
                WHERE id = ?
            """, (telegram_message_id, deal_id))
            conn.commit()
    
    def mark_deal_inactive(self, deal_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sent_deals 
                SET is_active = 0
                WHERE id = ?
            """, (deal_id,))
            conn.commit()
            logger.info(f"Marked deal #{deal_id} as inactive")
    
    def get_active_deals(self, hours: int = 72) -> List[SentDeal]:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM sent_deals 
                WHERE is_active = 1 AND sent_at > ?
                ORDER BY sent_at DESC
            """, (cutoff,))
            
            deals = []
            for row in cursor.fetchall():
                deals.append(SentDeal(
                    id=row['id'],
                    product_name=row['product_name'],
                    product_link=row['product_link'],
                    original_price=row['original_price'],
                    deal_price=row['deal_price'],
                    discount_percent=row['discount_percent'],
                    affiliate_link=row['affiliate_link'],
                    sent_at=datetime.fromisoformat(row['sent_at']),
                    telegram_message_id=row['telegram_message_id'],
                    is_active=bool(row['is_active']),
                    category=row['category'] or "",
                    section=row['section'] or ""
                ))
            
            return deals
    
    def get_deals_summary(self, hours: int = 24) -> Dict[str, Any]:
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as count, 
                       AVG(discount_percent) as avg_discount,
                       MIN(discount_percent) as min_discount,
                       MAX(discount_percent) as max_discount
                FROM sent_deals 
                WHERE sent_at > ?
            """, (cutoff,))
            
            stats = cursor.fetchone()
            
            cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM sent_deals 
                WHERE sent_at > ?
                GROUP BY category
            """, (cutoff,))
            
            by_category = {row['category']: row['count'] for row in cursor.fetchall()}
            
            return {
                "period_hours": hours,
                "total_deals": stats['count'],
                "avg_discount": stats['avg_discount'] or 0,
                "min_discount": stats['min_discount'] or 0,
                "max_discount": stats['max_discount'] or 0,
                "by_category": by_category
            }
    
    def record_price_check(self, product_link: str, price: float):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history (product_link, price)
                VALUES (?, ?)
            """, (product_link, price))
            conn.commit()
    
    def get_price_history(
        self, 
        product_link: str, 
        days: int = 30
    ) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price, checked_at 
                FROM price_history 
                WHERE product_link = ? AND checked_at > ?
                ORDER BY checked_at ASC
            """, (product_link, cutoff))
            
            return [
                {"price": row['price'], "checked_at": row['checked_at']}
                for row in cursor.fetchall()
            ]
    
    def cleanup_old_records(self, days: int = 90):
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM price_history WHERE checked_at < ?
            """, (cutoff,))
            price_deleted = cursor.rowcount
            
            cursor.execute("""
                UPDATE sent_deals SET is_active = 0 WHERE sent_at < ?
            """, (cutoff,))
            
            conn.commit()
            logger.info(f"Cleanup: removed {price_deleted} old price records")
    
    def get_config(self, key: str, default: str = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default
    
    def set_config(self, key: str, value: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            conn.commit()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tracker = DealsTracker("test_deals.db")
    
    deal_id = tracker.record_sent_deal(
        product_name="Test Product",
        product_link="https://s.click.aliexpress.com/e/_test123",
        original_price=100.0,
        deal_price=80.0,
        discount_percent=20.0,
        affiliate_link="https://s.click.aliexpress.com/e/_affiliate123",
        category="EARPHONES",
        section="in-ears"
    )
    
    print(f"Recorded deal with ID: {deal_id}")
    
    was_sent = tracker.was_deal_sent_recently(
        "https://s.click.aliexpress.com/e/_test123",
        hours=24
    )
    print(f"Was sent recently: {was_sent}")
    
    active = tracker.get_active_deals()
    print(f"Active deals: {len(active)}")
    
    summary = tracker.get_deals_summary()
    print(f"Summary: {summary}")
    
    os.remove("test_deals.db")

