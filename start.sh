#!/bin/bash
# Startup script for mARB 2.0

set -e

echo "Starting mARB 2.0..."

# Activate virtual environment
source venv/bin/activate

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration before starting the server"
fi

# Check if database URL is set
if grep -q "postgresql://user:password@localhost" .env; then
    echo "⚠️  Warning: Database URL appears to be using default values"
    echo "   Please update DATABASE_URL in .env"
fi

# Start the server
echo "🚀 Starting FastAPI server..."
python run.py

