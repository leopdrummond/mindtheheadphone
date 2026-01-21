# 🛒 AliExpress Deals Bot

Automated system that monitors AliExpress products from a Google Sheets spreadsheet and posts deals to a Telegram group/channel. **Optimized for the Brazilian market** with automatic tax calculation and BRL price display.

## ✨ Features

- 📊 **Google Sheets Integration**: Reads your product catalog from a public spreadsheet
- 🔍 **Price Monitoring**: Checks AliExpress for current prices using the official API
- 💰 **Deal Detection**: Identifies products with significant discounts (configurable threshold)
  - Uses spreadsheet prices as reference (more accurate than inflated AliExpress MSRP)
- 🇧🇷 **Brazilian Tax Calculation**: Automatically calculates and displays Brazilian import taxes
  - Up to US$50: 44% tax
  - Above US$50: 92% tax, minus US$20
- 💵 **BRL Currency Support**: All prices displayed in Brazilian Real (R$) with taxes included
- 🔗 **Affiliate Links**: Automatically generates affiliate links with your tracking ID
- 📱 **Telegram Notifications**: Posts formatted deal messages to your channel/group (UTF-8 encoding for proper accent mark display)
- 🚫 **Duplicate Prevention**: Tracks sent deals to avoid repetition
- 📋 **Deal Summaries**: Optional periodic summaries of active deals
- ⏰ **Scheduling**: Run as cron job or continuous service

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Google Sheets  │────▶│   Deals Bot      │────▶│    Telegram     │
│  (Products)     │     │  (Orchestrator)  │     │    Channel      │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │ AliExpress│ │  SQLite   │ │  Tracker  │
            │    API    │ │  Database │ │  (Dups)   │
            └───────────┘ └───────────┘ └───────────┘
```

## 📋 Requirements

- Python 3.9+
- AliExpress Affiliate API credentials
- Telegram Bot token
- Public Google Sheets spreadsheet

## 🚀 Quick Start

> **For detailed server deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)**

### 1. Install Dependencies

**First, install pip3 if not already installed:**
```bash
sudo apt install python3-pip
```

**Then install project dependencies:**
```bash
cd Aliexpress-telegram-bot
pip3 install -r requirements.txt
```

**Note:** On Linux, use `python3` and `pip3` instead of `python` and `pip`.

### 2. Configure Environment

```bash
# Copy example configuration
cp env.example .env

# Edit with your credentials
nano .env
```

### 3. Set Up Google Sheets

Your spreadsheet should have columns like:

| Produto | Assinatura Sonora | Disponibilidade | Preço Base | Impostos | Preço Final | Review | Link | Descrição |
|---------|-------------------|-----------------|------------|----------|-------------|--------|------|-----------|
| Product Name | Natural | Importado | 100.00 | 45 | R$ 145.00 | https://... | https://s.click.aliexpress... | Description |

**Important columns:**
- **Produto** (Column A): Product name
- **Preço Base** (Column D): Base price in BRL (for reference)
- **Preço Final** (Column F): **Reference price in BRL** - This is used as the baseline for deal detection (already includes taxes)
- **Link** (Column H): AliExpress affiliate link (s.click.aliexpress.com format)

**Important:** 
- The spreadsheet must be **publicly shared** (anyone with the link can view) for the bot to read it.
- **Preço Final (Column F)** is used as the reference price because AliExpress MSRP is often inflated and not representative of actual market prices.

### 4. Get Sheet GIDs

For each sheet tab you want to monitor:
1. Open the sheet in your browser
2. Look at the URL: `...spreadsheets/d/ID/edit#gid=XXXXXXX`
3. The number after `#gid=` is the GID

**Current spreadsheet configuration:**
- Spreadsheet ID: Set in `.env` as `GOOGLE_SPREADSHEET_ID`
- **EARPHONES**: `841822689` ✅ (configured in `deals_bot.py`)
<!-- - **HEADPHONES**: `362895356` ✅ (configured in `deals_bot.py`) -->
<!-- - **ELETRÔNICOS**: `1891840859` ✅ (configured in `deals_bot.py`) -->

**To use a different spreadsheet:**
1. Update `GOOGLE_SPREADSHEET_ID` in `.env`
2. Get GIDs from each sheet tab URL (`#gid=XXXXXXX`)
3. Update `DEFAULT_SHEET_GIDS` in `deals_bot.py`

All three sheets are already configured in `deals_bot.py`:

```python
DEFAULT_SHEET_GIDS = {
    "EARPHONES": 841822689,
   #  "HEADPHONES": 362895356,
   #  "ELETRÔNICOS": 1891840859,
}
```

### 5. Test Configuration

```bash
python3 deals_bot.py --mode test
```

### 6. Run a Check

```bash
# Check for deals and send to Telegram
python3 deals_bot.py --mode check

# Check without sending (dry run)
python3 deals_bot.py --mode check --no-send
```

## 📖 Usage

### Command Line Options

```bash
# Single check run
python3 deals_bot.py --mode check

# Check without sending
python3 deals_bot.py --mode check --no-send

# Limit number of deals
python3 deals_bot.py --mode check --max-deals 5

# Send summary of active deals
python3 deals_bot.py --mode summary

# Send daily statistics digest
python3 deals_bot.py --mode digest

# Run continuously (checks every 6 hours by default)
python3 deals_bot.py --mode continuous

# Run continuously with custom interval
python3 deals_bot.py --mode continuous --interval 4

# Test configuration
python3 deals_bot.py --mode test
```

### Setting Up Cron Jobs

```bash
# Edit crontab
crontab -e

# Add these lines:

# Check for deals every 6 hours
0 */6 * * * cd /path/to/Aliexpress-telegram-bot && /usr/bin/python3 deals_bot.py --mode check >> /var/log/deals_bot.log 2>&1

# Send summary at 10 AM and 6 PM
0 10,18 * * * cd /path/to/Aliexpress-telegram-bot && /usr/bin/python3 deals_bot.py --mode summary >> /var/log/deals_bot.log 2>&1

# Send daily digest at 9 PM
0 21 * * * cd /path/to/Aliexpress-telegram-bot && /usr/bin/python3 deals_bot.py --mode digest >> /var/log/deals_bot.log 2>&1

# Weekly database cleanup
0 3 * * 0 cd /path/to/Aliexpress-telegram-bot && /usr/bin/python3 deals_bot.py --mode check --cleanup-days 90 >> /var/log/deals_bot.log 2>&1
```

### Running as a Service (systemd)

Create `/etc/systemd/system/deals-bot.service`:

```ini
[Unit]
Description=AliExpress Deals Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Aliexpress-telegram-bot
ExecStart=/usr/bin/python3 deals_bot.py --mode continuous --interval 6
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable deals-bot
sudo systemctl start deals-bot
sudo systemctl status deals-bot
```

## 🔧 Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | Required |
| `TELEGRAM_CHANNEL_ID` | Target channel (@name or ID) | Required |
| `GOOGLE_SPREADSHEET_ID` | Spreadsheet ID from URL | Required |
| `ALIEXPRESS_APP_KEY` | AliExpress API key | Required |
| `ALIEXPRESS_APP_SECRET` | AliExpress API secret | Required |
| `ALIEXPRESS_TRACKING_ID` | Affiliate tracking ID | Required |
| `TARGET_CURRENCY` | API currency (BRL recommended for Brazil) | BRL |
| `TARGET_LANGUAGE` | Product language | en |
| `QUERY_COUNTRY` | Country for prices/shipping | BR |
| `USD_TO_BRL_RATE` | USD to BRL exchange rate (update periodically) | 5.0 |
| `MIN_DISCOUNT_PERCENT` | Minimum discount to notify | 10 |
| `MAX_DEALS_PER_RUN` | Max deals per check | 25 |
| `DUPLICATE_CHECK_HOURS` | Hours before re-sending | 24 |
| `MESSAGE_DELAY_SECONDS` | Delay between messages | 3 |
| `DEALS_DB_PATH` | SQLite database path | deals_history.db |

## 📁 File Structure

```
Aliexpress-telegram-bot/
├── deals_bot.py           # Main orchestrator (automated mode) ⭐
├── google_sheets.py       # Google Sheets reader
├── deals_checker.py       # Price checking logic
├── deals_tracker.py       # SQLite tracking
├── telegram_notifier.py   # Telegram messaging
├── brazil_taxes.py        # Brazilian tax calculation
├── iop/                   # AliExpress API SDK
│   ├── __init__.py
│   └── base.py
├── requirements.txt
├── .env                   # Configuration (create from env.example)
├── env.example            # Configuration template
├── README.md
├── DEPLOYMENT.md          # Server deployment guide
├── API_TESTING.md         # API testing guide and troubleshooting
├── CONTACT_ALIEXPRESS.md  # Guide for contacting AliExpress about API access
├── test_product.py        # Script to test product API access
├── deals-bot.service      # Systemd service file
├── setup_service.sh       # Service setup script
├── diagnose.py            # Diagnostic tool
├── test_api.py            # API test script
└── deals_history.db       # Created automatically
```

## 🔍 How It Works

1. **Fetch Products**: Reads your spreadsheet via CSV export (no API key needed for public sheets)

2. **Resolve Links**: Short AliExpress links (`s.click.aliexpress.com`) are resolved to get product IDs

3. **Check Prices**: Uses AliExpress Affiliate API to get current prices in BRL (or configured currency)

4. **Calculate Taxes**: Applies Brazilian import tax calculation:
   - Up to US$50: 44% tax
   - Above US$50: 92% tax, minus US$20

5. **Detect Deals**: Compares spreadsheet **Preço Final** (Column F) vs API current price (with taxes) to find discounts
   - Uses your spreadsheet price as reference (more accurate than inflated AliExpress MSRP)
   - Calculates discount percentage based on spreadsheet final price

6. **Filter Duplicates**: Checks SQLite database to avoid repeating recent deals

7. **Generate Links**: Creates affiliate links with your tracking ID

8. **Send to Telegram**: Posts formatted messages with:
   - Prices in BRL (with and without taxes)
   - Product images
   - Discount percentage
   - Buy buttons

## 📝 Notes

### Brazilian Tax Calculation

The bot automatically calculates Brazilian import taxes according to current regulations:
- **Up to US$50**: 44% tax on the product price
- **Above US$50**: 92% tax minus US$20

All prices are displayed in **Brazilian Real (R$)** with taxes included, making it easy for Brazilian customers to see the final cost.

### Exchange Rate

The USD to BRL exchange rate is configured in `.env`:
```bash
USD_TO_BRL_RATE=5.0
```

**Update this regularly** to reflect current exchange rates. You can:
- Update manually in `.env`
- Or implement automatic fetching (see `brazil_taxes.py`)

### Price Comparison

The bot uses **your spreadsheet's Preço Final (Column F)** as the reference price instead of AliExpress MSRP, which is often inflated. The comparison works as follows:

1. **Reference Price**: Spreadsheet **Preço Final** (Column F) - already includes Brazilian taxes
2. **Current Price**: AliExpress API current price + Brazilian import taxes
3. **Discount Calculation**: If current price (with taxes) is lower than spreadsheet final price by the minimum threshold, it's a deal

**Why use spreadsheet prices?**
- AliExpress sellers often show inflated MSRP that's never actually practiced
- Your spreadsheet prices reflect real market values
- More accurate deal detection based on actual pricing history

All prices are:
- Fetched in BRL from AliExpress API (if supported)
- Brazilian import taxes are added automatically to API prices
- Displayed in BRL format (R$ X.XXX,XX)

### Rate Limits

- AliExpress API: ~20 requests/second (handled by batch processing with 2s delays)
- Telegram: ~30 messages/second (handled by 3s delays between messages)
- Batch size: 5 products per batch to avoid rate limiting

## 🧪 Testing Product API Access

Before adding products to your spreadsheet, test if they're accessible via the AliExpress Affiliate API:

```bash
python3 test_product.py <product_id>
```

**Example:**
```bash
python3 test_product.py 3256809081965886
```

This tests the product with different API configurations and shows:
- ✅ If the product is accessible via API
- ⚠️ If the product exists but isn't API-accessible  
- ❌ API errors or configuration issues

**📖 For detailed testing guide, troubleshooting, and how to contact AliExpress, see:**
- **[API_TESTING.md](API_TESTING.md)** - Complete testing guide
- **[CONTACT_ALIEXPRESS.md](CONTACT_ALIEXPRESS.md)** - How to contact AliExpress about API access

### Troubleshooting

**No products found:**
- Check spreadsheet is publicly shared (View → Anyone with the link)
- Verify spreadsheet ID is correct in `.env`
- Check GIDs match actual sheets (from URL `#gid=XXXXXXX`)
- Check internet connection (spreadsheet fetch requires network)

**No deals found:**
- Lower `MIN_DISCOUNT_PERCENT` to test (e.g., `--mode check --no-send`)
- Verify AliExpress API credentials are correct
- Check if API app is approved (not in "Test" status)
- Check product links are valid AliExpress links
- API may be rate-limited (wait and retry)

**Telegram errors:**
- Verify bot is admin in channel with "Post Messages" permission
- Check channel ID format (numeric ID or @channel_name)
- Test bot connection: `python3 deals_bot.py --mode test`

**Price/Tax calculation issues:**
- Update `USD_TO_BRL_RATE` in `.env` with current exchange rate
- Verify `TARGET_CURRENCY=BRL` and `QUERY_COUNTRY=BR` in `.env`
- Check `brazil_taxes.py` for tax calculation logic
- Ensure spreadsheet **Preço Final** (Column F) is correctly populated

**Character encoding issues:**
- Bot uses UTF-8 encoding for all text (handles Portuguese accent marks correctly)
- If you see encoding issues, verify spreadsheet is saved with UTF-8 encoding

**API rate limiting:**
- Bot automatically handles rate limits with delays
- Reduce batch size if needed (edit `deals_checker.py`)
- Wait between runs if hitting limits frequently

## 🇧🇷 Brazilian Market Features

### Tax Calculation

The bot automatically calculates Brazilian import taxes according to current regulations:

**Tax Rules:**
- **Up to US$50**: 44% tax on the product price
- **Above US$50**: 92% tax, minus US$20 discount

**Examples:**
- Product: $30 USD → Tax: $13.20 (44%) → Final: R$ 216,00 (at 5.0 exchange rate)
- Product: $50 USD → Tax: $22.00 (44%) → Final: R$ 360,00 (at 5.0 exchange rate)
- Product: $75 USD → Tax: $49.00 (92% - $20) → Final: R$ 620,00 (at 5.0 exchange rate)
- Product: $100 USD → Tax: $72.00 (92% - $20) → Final: R$ 860,00 (at 5.0 exchange rate)

### Price Display

All prices are displayed in **Brazilian Real (R$)** format:
- **Preço com impostos (BRL)**: Final price including all Brazilian import taxes
- **Preço sem impostos (BRL)**: Base price before taxes (converted from USD if needed)

This makes it easy for Brazilian customers to see the **total cost** they'll pay, including all import fees.

### Configuration

For Brazilian market, ensure these settings in `.env`:
```bash
# Request prices in BRL from AliExpress API
TARGET_CURRENCY=BRL
QUERY_COUNTRY=BR

# USD to BRL exchange rate (update periodically)
USD_TO_BRL_RATE=5.0
```

**Updating Exchange Rate:**
- Check current rate at: https://www.xe.com/currencyconverter/convert/?Amount=1&From=USD&To=BRL
- Update `USD_TO_BRL_RATE` in `.env`
- Or implement automatic fetching (see `brazil_taxes.py` for API option)

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

---

Made with ❤️ for Brazilian deal hunters 🇧🇷
