#!/bin/bash

# ChatGPT Scraper Setup and Run Script
# This script sets up the environment and runs the scraper

# set -e  # Exit on any error (disabled for Chrome startup)

echo "🚀 Setting up ChatGPT Scraper environment..."



echo "🔄 Killing existing Chrome processes..."
pkill -f "Google Chrome" 2>/dev/null || true
pkill -f "Chrome Helper" 2>/dev/null || true
pkill -f "GoogleUpdater" 2>/dev/null || true
sleep 2

echo "🌐 Starting Chrome with remote debugging..."
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/tmp_chrome_debug" --no-first-run --no-default-browser-check > /dev/null 2>&1 &

# Wait for Chrome to start
echo "⏳ Waiting for Chrome to start..."
sleep 3



# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first."
    echo "Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Initialize uv project if not already done
if [ ! -f "pyproject.toml" ]; then
    echo "📋 Initializing uv project..."
    uv init
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🐍 Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

echo "📦 Installing dependencies with uv..."
uv add playwright requests

echo "🔄 Syncing project environment..."
uv sync

echo "🌐 Installing Playwright browser binaries..."
uv run python -m playwright install

echo "✅ Setup complete! Checking Chrome connection..."
echo "----------------------------------------"

# Verify Chrome is running with remote debugging
if curl -s http://localhost:9222/json > /dev/null 2>&1; then
    echo "✅ Chrome is running with remote debugging on port 9222"
else
    echo "❌ Chrome remote debugging not available. Please check Chrome startup."
    exit 1
fi

echo "🔍 Running scraper..."
# Run the scraper
uv run python scrape.py

echo "----------------------------------------"
echo "✅ Scraping completed successfully!"
echo "📁 Check the Downloaded_Chats/ directory for your files."
