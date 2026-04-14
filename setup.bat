@echo off
REM Automated Setup Script for Panopto Downloader (Windows)
REM This script sets up everything automatically!

echo.
echo ========================================
echo    Panopto Downloader - Setup
echo ========================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 or later from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    Found Python %PYTHON_VERSION%

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install package
echo Installing panopto-downloader and dependencies...
pip install -e . >nul 2>&1

REM Verify installation
echo.
echo Verifying installation...
panopto-downloader --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Installation verification failed
    pause
    exit /b 1
)

for /f "delims=" %%i in ('panopto-downloader --version') do set VERSION=%%i
echo    %VERSION%

echo.
echo ========================================
echo          Setup Complete!
echo ========================================
echo.
echo Quick Start:
echo.
echo   1. Create a config file:
echo      venv\Scripts\activate
echo      panopto-downloader init -o my_course.yaml
echo.
echo   2. Edit my_course.yaml to add your lecture URLs
echo.
echo   3. Log into Panopto in Chrome, close Chrome, then:
echo      panopto-downloader -c my_course.yaml download
echo.
echo For detailed help, see README.md or run:
echo    panopto-downloader --help
echo.
echo In future terminal sessions, activate venv with:
echo    venv\Scripts\activate
echo.
pause
