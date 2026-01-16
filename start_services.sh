#!/bin/bash
# Start all mARB 2.0 services with proper environment
#
# This script sets up the environment and provides instructions for starting
# all required services (Redis, Celery, FastAPI) for mARB 2.0.
#
# Usage:
#   ./start_services.sh        # Show instructions for starting services
#   ./start_services.sh api     # Start the FastAPI server directly
#
# Prerequisites:
#   - Virtual environment at venv/
#   - PostgreSQL installed and running
#   - Redis installed (can be started separately)
#   - .env file with configuration (optional, will use defaults if missing)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting mARB 2.0 Services${NC}"
echo "================================"

# Load .env if it exists (load before setting other env vars)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if PostgreSQL is running
# Use DATABASE_USER from .env if available, otherwise default to current user
DATABASE_USER="${DATABASE_USER:-${USER:-postgres}}"
if ! pg_isready -U "${DATABASE_USER}" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  PostgreSQL not running. Starting...${NC}"
    brew services start postgresql@14 2>/dev/null || {
        echo -e "${YELLOW}   Could not start PostgreSQL automatically.${NC}"
        echo "   Please start it manually: brew services start postgresql@14"
    }
    sleep 2
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Redis not running. Please start it in another terminal:${NC}"
    echo "   redis-server"
    echo ""
fi

# Activate virtual environment
# IMPORTANT: Activate venv before setting PATH to ensure Python packages are available
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found at venv/${NC}"
    echo "   Please create it first: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# Ensure postgres is added to the path after venv activation
# This ensures PostgreSQL tools are available while maintaining venv priority
export PATH="/usr/local/opt/postgresql@14/bin:/opt/homebrew/opt/postgresql@14/bin:$PATH"

echo ""
echo "Services ready! Use these commands in separate terminals:"
echo ""
echo -e "${GREEN}Terminal 1 - Redis:${NC}"
echo "   redis-server"
echo ""
echo -e "${GREEN}Terminal 2 - Celery Worker:${NC}"
echo "   # IMPORTANT: Activate virtual environment first"
echo "   source venv/bin/activate"
echo "   # Then start Celery worker"
echo "   celery -A app.services.queue.tasks worker --loglevel=info"
echo ""
echo -e "${GREEN}Terminal 3 - FastAPI Server:${NC}"
echo "   # IMPORTANT: Activate virtual environment first"
echo "   source venv/bin/activate"
echo "   # Then start the API server"
echo "   python run.py"
echo ""
echo -e "${YELLOW}Important Notes:${NC}"
echo "   • Always activate the virtual environment (source venv/bin/activate) before"
echo "     starting Celery or FastAPI services"
echo "   • The .env file will be automatically loaded if present"
echo "   • Make sure PostgreSQL and Redis are running before starting services"
echo ""
echo -e "${GREEN}Or run this script to start FastAPI directly:${NC}"
echo "   ./start_services.sh api"
echo ""

# If argument is "api", start the API server
if [ "$1" == "api" ]; then
    echo -e "${GREEN}Starting FastAPI server...${NC}"
    python run.py
fi

