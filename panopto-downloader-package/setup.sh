#!/bin/bash
# Automated Setup Script for Panopto Downloader
# This script sets up everything automatically!

set -e  # Exit on any error

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   Panopto Downloader - Automated Setup        ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "🔍 Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.12 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "   Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install package
echo "📥 Installing panopto-downloader and dependencies..."
pip install -e . > /dev/null 2>&1

# Verify installation
echo ""
echo "✅ Verifying installation..."
if panopto-downloader --version > /dev/null 2>&1; then
    VERSION=$(panopto-downloader --version)
    echo "   $VERSION"
else
    echo "❌ Installation verification failed"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║          ✅ Setup Complete! ✅                 ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "🚀 Quick Start:"
echo ""
echo "   1. Create a config file:"
echo "      source venv/bin/activate"
echo "      panopto-downloader init -o my_course.yaml"
echo ""
echo "   2. Edit my_course.yaml to add your lecture URLs"
echo ""
echo "   3. Log into Panopto in Chrome, close Chrome, then:"
echo "      panopto-downloader -c my_course.yaml download"
echo ""
echo "📖 For detailed help, see README.md or run:"
echo "   panopto-downloader --help"
echo ""
echo "💡 In future terminal sessions, remember to activate venv:"
echo "   source venv/bin/activate"
echo ""
