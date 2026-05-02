# Automated Setup Script for Panopto Downloader (PowerShell)
# This script sets up everything automatically!

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Panopto Downloader - Automated Setup        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "🔍 Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "   Please install Python 3.12 or later from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip | Out-Null

# Install package
Write-Host "📥 Installing panopto-downloader and dependencies..." -ForegroundColor Yellow
pip install -e . | Out-Null

# Verify installation
Write-Host ""
Write-Host "✅ Verifying installation..." -ForegroundColor Yellow
try {
    $version = panopto-downloader --version 2>&1
    Write-Host "   $version" -ForegroundColor Green
} catch {
    Write-Host "❌ Installation verification failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║          ✅ Setup Complete! ✅                 ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Quick Start:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   1. Create a config file:" -ForegroundColor White
Write-Host "      .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "      panopto-downloader init -o my_course.yaml" -ForegroundColor Gray
Write-Host ""
Write-Host "   2. Edit my_course.yaml to add your lecture URLs" -ForegroundColor White
Write-Host ""
Write-Host "   3. Log into Panopto in Chrome, close Chrome, then:" -ForegroundColor White
Write-Host "      panopto-downloader -c my_course.yaml download" -ForegroundColor Gray
Write-Host ""
Write-Host "📖 For detailed help, see README.md or run:" -ForegroundColor Cyan
Write-Host "   panopto-downloader --help" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 In future PowerShell sessions, activate venv with:" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host ""
