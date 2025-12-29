#!/bin/bash
# Quick setup script for systemd service

echo "🚀 Setting up AliExpress Deals Bot as systemd service..."
echo ""

# Get current directory
BOT_DIR=$(pwd)
BOT_USER=$(whoami)

echo "Bot directory: $BOT_DIR"
echo "Bot user: $BOT_USER"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script needs sudo privileges to install systemd service"
    echo ""
    echo "Please run:"
    echo "  sudo $0"
    exit 1
fi

# Create service file
SERVICE_FILE="/etc/systemd/system/deals-bot.service"

echo "Creating service file: $SERVICE_FILE"
cat > $SERVICE_FILE <<EOF
[Unit]
Description=AliExpress Deals Bot - Automated Deal Monitoring
After=network.target

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 deals_bot.py --mode continuous --interval 6
Restart=always
RestartSec=10
StandardOutput=append:/var/log/deals-bot.log
StandardError=append:/var/log/deals-bot-error.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created"
echo ""

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload
echo "✅ Systemd reloaded"
echo ""

# Enable service
echo "Enabling service (start on boot)..."
systemctl enable deals-bot
echo "✅ Service enabled"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Make sure your .env file is configured"
echo "  2. Test the bot: python3 deals_bot.py --mode test"
echo "  3. Start the service: sudo systemctl start deals-bot"
echo "  4. Check status: sudo systemctl status deals-bot"
echo "  5. View logs: sudo journalctl -u deals-bot -f"
echo ""
echo "Useful commands:"
echo "  sudo systemctl start deals-bot      # Start bot"
echo "  sudo systemctl stop deals-bot       # Stop bot"
echo "  sudo systemctl restart deals-bot   # Restart bot"
echo "  sudo systemctl status deals-bot    # Check status"
echo "  sudo journalctl -u deals-bot -f    # View live logs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"




