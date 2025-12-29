#!/bin/bash
# Setup script for AliExpress Deals Bot

echo "🚀 Setting up AliExpress Deals Bot..."
echo ""

# Check if pip3 is installed
if ! command -v pip3 &> /dev/null; then
    echo "📦 Installing pip3..."
    sudo apt update
    sudo apt install python3-pip -y
fi

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

echo "✅ Python $(python3 --version) found"
echo "✅ pip3 $(pip3 --version | cut -d' ' -f2) found"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy env.example to .env: cp env.example .env"
echo "2. Edit .env with your credentials: nano .env"
echo "3. Test configuration: python3 deals_bot.py --mode test"
echo "4. Run deals check: python3 deals_bot.py --mode check --no-send"

