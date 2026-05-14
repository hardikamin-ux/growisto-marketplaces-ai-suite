#!/bin/bash
# Amazon India Review Scraper — Mac Installer
# Run this once after extracting the zip file.
# Right-click → Open, then click "Open" on the security prompt.

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

clear
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Amazon India Review Scraper            ║"
echo "  ║   One-time Mac Installer · Growisto      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Python 3 ─────────────────────────────────────────────────────────
echo "  [1/5] Checking Python 3..."

if ! command -v python3 &>/dev/null; then
    echo ""
    echo "  ❌  Python 3 was not found on this machine."
    echo ""
    echo "  Please install it from:"
    echo "     https://www.python.org/downloads/"
    echo ""
    echo "  After installing Python, run this installer again."
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi

PYVER=$(python3 --version 2>&1)
echo "  ✅  Found $PYVER"

# ── Step 2: pip packages ──────────────────────────────────────────────────────
echo ""
echo "  [2/5] Installing Python packages..."
echo "        (this may take 1–2 minutes)"
echo ""

python3 -m pip install --upgrade pip --quiet 2>&1 | grep -v "^$" | sed 's/^/         /'

python3 -m pip install \
    playwright \
    playwright-stealth \
    beautifulsoup4 \
    openpyxl \
    lxml \
    pandas \
    streamlit \
    --quiet 2>&1 | grep -v "^$" | sed 's/^/         /'

# Force-reinstall numpy to avoid source-directory import errors
python3 -m pip install --upgrade --force-reinstall numpy --quiet 2>&1 | grep -v "^$" | sed 's/^/         /'

echo ""
echo "  ✅  Packages installed"

# ── Step 3: Playwright browser ───────────────────────────────────────────────
echo ""
echo "  [3/5] Installing Chrome automation browser..."
echo "        (one-time download, ~150 MB)"
echo ""

python3 -m playwright install chromium 2>&1 | sed 's/^/         /'

echo ""
echo "  ✅  Chrome installed"

# ── Step 4: Copy app to permanent home folder ─────────────────────────────────
echo ""
echo "  [4/5] Installing app to ~/AmazonScraper..."

APP_DIR="$HOME/AmazonScraper"
mkdir -p "$APP_DIR"

rsync -a --exclude='.git' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.DS_Store' \
    "$DIR/" "$APP_DIR/" 2>/dev/null || \
cp -r "$DIR/." "$APP_DIR/"

echo "  ✅  App installed to ~/AmazonScraper"

# ── Step 5: Create Desktop shortcut (.command) ───────────────────────────────
echo ""
echo "  [5/5] Creating Desktop shortcut..."

# Handle iCloud Desktop (common on modern Macs)
if [ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Desktop" ]; then
    DESKTOP="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Desktop"
else
    DESKTOP="$HOME/Desktop"
fi

SHORTCUT="$DESKTOP/Amazon Scraper.command"

cat > "$SHORTCUT" << LAUNCHER
#!/bin/bash
APP_DIR="\$HOME/AmazonScraper"

# Kill any previous instance on port 8501
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

echo "Starting Amazon India Review Scraper..."
cd "\$APP_DIR"
python3 -m streamlit run webapp.py \\
    --server.port 8501 \\
    --server.headless true &
STREAMLIT_PID=\$!

sleep 3
open "http://localhost:8501"

echo "App running at http://localhost:8501"
echo "Close this window to stop the scraper."
wait \$STREAMLIT_PID
LAUNCHER

chmod +x "$SHORTCUT"

# Reveal in Finder so user can see it
open -R "$SHORTCUT" 2>/dev/null || true

echo ""
echo "  ✅  Shortcut created on Desktop: 'Amazon Scraper.command'"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Setup complete! 🎉                     ║"
echo "  ║                                          ║"
echo "  ║   Double-click 'Amazon Scraper.command'  ║"
echo "  ║   on your Desktop to launch the tool.   ║"
echo "  ║                                          ║"
echo "  ║   Finder has opened to show you where.  ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
read -p "  Press Enter to close this window..."
