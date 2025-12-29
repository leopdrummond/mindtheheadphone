import logging
import os
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from deals_checker import Deal
from deals_tracker import DealsTracker, SentDeal
from brazil_taxes import calculate_final_price_brl, format_brl_price, get_exchange_rate, calculate_brazilian_tax

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')


class TelegramNotifier:
   
    
    def __init__(
        self,
        bot_token: str = None,
        channel_id: str = None,
        tracker: DealsTracker = None
    ):
       
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.channel_id = channel_id or TELEGRAM_CHANNEL_ID
        self.tracker = tracker
        
        if not self.bot_token:
            raise ValueError("Telegram bot token is required")
        
        self.bot = Bot(token=self.bot_token)
        logger.info(f"Telegram notifier initialized for channel: {self.channel_id}")
    
    def _format_price(self, price: float, currency: str = "USD") -> str:
       
        if currency == "BRL":
            return f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif currency == "USD":
            return f"${price:,.2f}"
        else:
            return f"{currency} {price:,.2f}"
    
    def _format_deal_message(self, deal: Deal) -> str:
       
        title = deal.title or deal.product.name
        
        if len(title) > 200:
            title = title[:197] + "..."
        
        exchange_rate = get_exchange_rate()
        
        original_final_brl = deal.original_price
        
        if deal.currency.upper() == 'BRL':
            current_price_usd = deal.current_price / exchange_rate
            current_base_brl = deal.current_price
        else:
            current_price_usd = deal.current_price
            current_base_brl = deal.current_price * exchange_rate
        
        current_tax_usd = calculate_brazilian_tax(current_price_usd)
        current_tax_brl = current_tax_usd * exchange_rate
        current_final_brl = current_base_brl + current_tax_brl
        
        if deal.product.base_price > 0:
            original_base_brl = deal.product.base_price
        else:
            original_base_brl = original_final_brl / 1.5
        
        original_price_brl_str = format_brl_price(original_final_brl)
        current_price_brl_str = format_brl_price(current_final_brl)
        
        original_price_brl_no_tax = format_brl_price(original_base_brl)
        current_price_brl_no_tax = format_brl_price(current_base_brl)
        
        lines = [
            f"🔥 <b>OFERTA!</b> 🔥",
            "",
            f"📦 <b>{title}</b>",
            "",
            f"💰 <b>Preço com impostos (BRL):</b>",
            f"   <s>{original_price_brl_str}</s> → <b>{current_price_brl_str}</b>",
            "",
            f"💵 <i>Preço sem impostos (BRL):</i>",
            f"   <s>{original_price_brl_no_tax}</s> → {current_price_brl_no_tax}",
            "",
            f"📉 <b>{deal.discount_percent:.0f}% OFF</b>",
            "",
        ]
        
        if deal.product.category or deal.product.section:
            category_info = []
            if deal.product.category:
                category_info.append(deal.product.category)
            if deal.product.section:
                category_info.append(deal.product.section)
            lines.append(f"🏷️ {' • '.join(category_info)}")
            lines.append("")
        
        if deal.product.description and len(deal.product.description) < 200:
            lines.append(f"📝 <i>{deal.product.description}</i>")
            lines.append("")
        
        lines.append(f"🛒 <a href=\"{deal.affiliate_link}\">COMPRAR AGORA</a>")
        lines.append("")
        lines.append(f"⏰ Verificado: {deal.checked_at.strftime('%d/%m %H:%M')}")
        
        return "\n".join(lines)
    
    def _format_summary_message(self, deals: List[SentDeal]) -> str:
        
        if not deals:
            return "📋 <b>Resumo de Ofertas</b>\n\nNenhuma oferta ativa no momento."
        
        lines = [
            "📋 <b>OFERTAS AINDA ATIVAS!</b>",
            f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
            f"🔥 <b>{len(deals)} ofertas encontradas:</b>",
            ""
        ]
        
        by_category: Dict[str, List[SentDeal]] = {}
        for deal in deals:
            category = deal.category or "Outros"
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(deal)
        
        for category, category_deals in by_category.items():
            lines.append(f"<b>📁 {category}</b>")
            
            for deal in category_deals[:5]:
                discount_str = f"{deal.discount_percent:.0f}%"
                
                exchange_rate = get_exchange_rate()
                final_brl, _, _ = calculate_final_price_brl(deal.deal_price, exchange_rate)
                price_str = format_brl_price(final_brl)
                
                hours_ago = deal.age_hours
                time_str = f"{int(hours_ago)}h" if hours_ago < 24 else f"{int(hours_ago/24)}d"
                
                lines.append(
                    f"  • {deal.product_name[:40]}{'...' if len(deal.product_name) > 40 else ''}"
                )
                lines.append(f"    💰 {price_str} (-{discount_str}) • {time_str} atrás")
                lines.append(f"    🔗 <a href=\"{deal.affiliate_link}\">Ver oferta</a>")
            
            if len(category_deals) > 5:
                lines.append(f"    <i>+ {len(category_deals) - 5} mais...</i>")
            
            lines.append("")
        
        lines.append("💡 <i>Ofertas podem expirar a qualquer momento!</i>")
        
        return "\n".join(lines)
    
    def _create_deal_keyboard(self, deal: Deal) -> InlineKeyboardMarkup:
        keyboard = []
        
        if deal.affiliate_link and deal.affiliate_link.startswith('http'):
            keyboard.append([
                InlineKeyboardButton("🛒 Comprar", url=deal.affiliate_link),
            ])
            
            if deal.product.review_link and deal.product.review_link.startswith('http'):
                keyboard[0].append(
                    InlineKeyboardButton("📺 Review", url=deal.product.review_link)
                )
        elif deal.product.review_link and deal.product.review_link.startswith('http'):
            keyboard.append([
                InlineKeyboardButton("📺 Review", url=deal.product.review_link)
            ])
        
        return InlineKeyboardMarkup(keyboard) if keyboard else None
    
    def _create_summary_keyboard(self) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("🔥 Ver Todas", url="https://aliexpress.com"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def send_deal(
        self,
        deal: Deal,
        channel_id: str = None
    ) -> Optional[int]:
       
        target_channel = channel_id or self.channel_id
        
        if not target_channel:
            logger.error("No channel ID configured")
            return None
        
        try:
            message_text = self._format_deal_message(deal)
            keyboard = self._create_deal_keyboard(deal)
            
            if not keyboard:
                logger.warning(f"Skipping {deal.product.name} - no valid affiliate link")
                return None
            
            if deal.image_url:
                try:
                    sent_message = await self.bot.send_photo(
                        chat_id=target_channel,
                        photo=deal.image_url,
                        caption=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
                    logger.info(f"Sent deal with image: {deal.product.name}")
                    
                    if self.tracker:
                        deal_id = self.tracker.record_sent_deal(
                            product_name=deal.product.name,
                            product_link=deal.product.aliexpress_link,
                            original_price=deal.original_price,
                            deal_price=deal.current_price,
                            discount_percent=deal.discount_percent,
                            affiliate_link=deal.affiliate_link,
                            telegram_message_id=sent_message.message_id,
                            category=deal.product.category,
                            section=deal.product.section,
                            product_id=deal.product_id
                        )
                        logger.debug(f"Recorded deal with ID: {deal_id}")
                    
                    return sent_message.message_id
                    
                except TelegramError as photo_error:
                    logger.warning(f"Failed to send photo, falling back to text: {photo_error}")
            
            sent_message = await self.bot.send_message(
                chat_id=target_channel,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            
            logger.info(f"Sent deal as text: {deal.product.name}")
            
            if self.tracker:
                deal_id = self.tracker.record_sent_deal(
                    product_name=deal.product.name,
                    product_link=deal.product.aliexpress_link,
                    original_price=deal.original_price,
                    deal_price=deal.current_price,
                    discount_percent=deal.discount_percent,
                    affiliate_link=deal.affiliate_link,
                    telegram_message_id=sent_message.message_id,
                    category=deal.product.category,
                    section=deal.product.section,
                    product_id=deal.product_id
                )
            
            return sent_message.message_id
            
        except TelegramError as e:
            logger.error(f"Failed to send deal {deal.product.name}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error sending deal: {e}")
            return None
    
    async def send_deals_batch(
        self,
        deals: List[Deal],
        channel_id: str = None,
        delay_seconds: float = 2.0,
        max_deals: int = 10
    ) -> List[int]:
       
        message_ids = []
        
        for i, deal in enumerate(deals[:max_deals]):
            message_id = await self.send_deal(deal, channel_id)
            
            if message_id:
                message_ids.append(message_id)
            
            if i < len(deals) - 1:
                await asyncio.sleep(delay_seconds)
        
        logger.info(f"Sent {len(message_ids)}/{len(deals)} deals successfully")
        return message_ids
    
    async def send_summary(
        self,
        active_deals: List[SentDeal] = None,
        channel_id: str = None
    ) -> Optional[int]:

        target_channel = channel_id or self.channel_id
        
        if not target_channel:
            logger.error("No channel ID configured")
            return None
        
        if active_deals is None and self.tracker:
            active_deals = self.tracker.get_active_deals(hours=48)
        
        if not active_deals:
            logger.info("No active deals for summary")
            return None
        
        try:
            message_text = self._format_summary_message(active_deals)
            keyboard = self._create_summary_keyboard()
            
            sent_message = await self.bot.send_message(
                chat_id=target_channel,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            
            logger.info(f"Sent summary with {len(active_deals)} deals")
            return sent_message.message_id
            
        except TelegramError as e:
            logger.error(f"Failed to send summary: {e}")
            return None
    
    async def send_daily_digest(
        self,
        channel_id: str = None
    ) -> Optional[int]:
      
        if not self.tracker:
            logger.error("Tracker not configured for daily digest")
            return None
        
        target_channel = channel_id or self.channel_id
        
        summary = self.tracker.get_deals_summary(hours=24)
        
        lines = [
            "📊 <b>RESUMO DIÁRIO DE OFERTAS</b>",
            f"📅 {datetime.now().strftime('%d/%m/%Y')}",
            "",
            f"🔢 Total de ofertas: <b>{summary['total_deals']}</b>",
            f"📉 Desconto médio: <b>{summary['avg_discount']:.1f}%</b>",
            f"🏆 Maior desconto: <b>{summary['max_discount']:.1f}%</b>",
            ""
        ]
        
        if summary['by_category']:
            lines.append("<b>Por categoria:</b>")
            for cat, count in summary['by_category'].items():
                lines.append(f"  • {cat}: {count} ofertas")
        
        lines.append("")
        lines.append("💡 <i>Fique ligado para mais ofertas!</i>")
        
        try:
            sent_message = await self.bot.send_message(
                chat_id=target_channel,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML
            )
            
            logger.info("Sent daily digest")
            return sent_message.message_id
            
        except TelegramError as e:
            logger.error(f"Failed to send daily digest: {e}")
            return None
    
    async def test_connection(self) -> bool:
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"Bot connected: @{bot_info.username}")
            
            if self.channel_id:
                try:
                    chat = await self.bot.get_chat(self.channel_id)
                    logger.info(f"Channel access confirmed: {chat.title or chat.id}")
                except TelegramError as e:
                    logger.warning(f"Could not access channel {self.channel_id}: {e}")
                    return False
            
            return True
            
        except TelegramError as e:
            logger.error(f"Bot connection failed: {e}")
            return False


async def main():
    logging.basicConfig(level=logging.INFO)
    
    tracker = DealsTracker("test_notifier.db")
    
    notifier = TelegramNotifier(tracker=tracker)
    
    connected = await notifier.test_connection()
    print(f"Bot connected: {connected}")
    
    if connected and TELEGRAM_CHANNEL_ID:
        from google_sheets import Product
        
        test_product = Product(
            name="Test Product - DELETE THIS",
            category="TEST",
            section="test",
            base_price=100.0,
            final_price=145.0,
            tax_rate=45.0,
            aliexpress_link="https://example.com",
            description="This is a test deal"
        )
        
        test_deal = Deal(
            product=test_product,
            current_price=75.0,
            original_price=100.0,
            discount_percent=25.0,
            discount_amount=25.0,
            currency="USD",
            affiliate_link="https://example.com/affiliate",
            product_id="123456"
        )
        
    
    import os
    if os.path.exists("test_notifier.db"):
        os.remove("test_notifier.db")


if __name__ == "__main__":
    asyncio.run(main())

