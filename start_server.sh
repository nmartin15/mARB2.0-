#!/bin/bash
# Start the FastAPI server (kills any existing process on port 8000 first)

set -e

echo "Starting mARB 2.0 server..."

# Check if port 8000 is in use
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use. Killing existing process..."
    kill -9 $(lsof -ti:8000) 2>/dev/null || true
    sleep 2
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please create it first:"
    echo "   python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. You may need to create one."
fi

echo "✅ Starting server on http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

# Start the server
python run.py

