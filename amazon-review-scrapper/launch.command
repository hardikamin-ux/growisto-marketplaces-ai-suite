#!/bin/bash
# Amazon India Review Scraper — Launcher
# Double-click this file to start the web app.

cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &>/dev/null; then
    osascript -e 'display alert "Python 3 not found" message "Please install Python 3 from python.org and run the installer again."'
    exit 1
fi

# Check dependencies
python3 -c "import streamlit, playwright, bs4, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    osascript -e 'display alert "Dependencies missing" message "Please run install-mac.command first to set up the scraper."'
    exit 1
fi

# Start Streamlit in the background
echo "Starting Amazon India Review Scraper..."
streamlit run webapp.py --server.port 8501 --server.headless true &
STREAMLIT_PID=$!

# Wait briefly then open the browser
sleep 3
open "http://localhost:8501"

echo "App running at http://localhost:8501"
echo "Close this window to stop the scraper."

# Keep alive until window is closed
wait $STREAMLIT_PID
