@echo off
title Amazon India Review Scraper — Windows Installer
color 0B
chcp 65001 >nul 2>&1

set "APPDIR=%~dp0"

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   Amazon India Review Scraper            ║
echo   ║   One-time Windows Installer · Growisto  ║
echo   ╚══════════════════════════════════════════╝
echo.

:: ── Step 1: Python ───────────────────────────────────────────────────────────
echo   [1/4] Checking Python 3...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Python 3 was not found on this machine.
    echo.
    echo   Please install it from:
    echo      https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: During install, check the box that says
    echo     "Add Python to PATH"
    echo.
    echo   After installing Python, run this installer again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   OK  Found %%v

:: ── Step 2: pip packages ──────────────────────────────────────────────────────
echo.
echo   [2/4] Installing Python packages...
echo         (this may take 1-2 minutes)
echo.

python -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo   WARNING: pip upgrade failed, continuing anyway...
)

python -m pip install ^
    playwright ^
    playwright-stealth ^
    beautifulsoup4 ^
    openpyxl ^
    lxml ^
    pandas ^
    streamlit ^
    --quiet

if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Package installation failed.
    echo   Check your internet connection and try again.
    pause
    exit /b 1
)

echo   OK  Packages installed

:: ── Step 3: Playwright browser ───────────────────────────────────────────────
echo.
echo   [3/4] Installing Chrome automation browser...
echo         (one-time download, ~150 MB)
echo.

python -m playwright install chromium

if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Chrome installation failed.
    pause
    exit /b 1
)

echo   OK  Chrome installed

:: ── Step 4: Desktop shortcut ─────────────────────────────────────────────────
echo.
echo   [4/4] Creating Desktop shortcut...

set "SHORTCUT=%USERPROFILE%\Desktop\Amazon Scraper.bat"

(
    echo @echo off
    echo title Amazon India Review Scraper
    echo cd /d "%APPDIR%"
    echo echo Starting Amazon India Review Scraper...
    echo start "" python -m streamlit run webapp.py --server.port 8501 --server.headless true
    echo timeout /t 4 /nobreak ^>nul
    echo start "" "http://localhost:8501"
    echo echo.
    echo echo App running at http://localhost:8501
    echo echo Close this window to stop the scraper.
    echo pause
) > "%SHORTCUT%"

echo   OK  Desktop shortcut created

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   Setup complete!                        ║
echo   ║                                          ║
echo   ║   Double-click 'Amazon Scraper' on       ║
echo   ║   your Desktop to launch the tool.       ║
echo   ╚══════════════════════════════════════════╝
echo.
pause
