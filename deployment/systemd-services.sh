#!/bin/bash
# Script to create systemd service files for mARB 2.0
# Run with: sudo bash deployment/systemd-services.sh
# 
# Configuration can be overridden via environment variables:
#   APP_DIR: Application directory (default: /opt/marb2.0)
#   APP_USER: Application user (default: marb)
#   VENV_PATH: Virtual environment path (default: $APP_DIR/venv)
#   API_HOST: API server host (default: 127.0.0.1)
#   API_PORT: API server port (default: 8000)
#   API_WORKERS: Number of uvicorn workers (default: 4)
#   CELERY_CONCURRENCY: Celery worker concurrency (default: 4)
#   FLOWER_PORT: Flower monitoring port (default: 5555)
#   REDIS_HOST: Redis host (default: localhost)
#   REDIS_PORT: Redis port (default: 6379)
#   REDIS_DB: Redis database number (default: 0)

# Use environment variables or defaults
APP_DIR="${APP_DIR:-/opt/marb2.0}"
APP_USER="${APP_USER:-marb}"
VENV_PATH="${VENV_PATH:-$APP_DIR/venv}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
API_WORKERS="${API_WORKERS:-4}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
FLOWER_PORT="${FLOWER_PORT:-5555}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"

# Validate configuration
if [ ! -d "$APP_DIR" ]; then
    echo "Error: Application directory does not exist: $APP_DIR"
    echo "Set APP_DIR environment variable or ensure default path exists"
    exit 1
fi

if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment does not exist: $VENV_PATH"
    echo "Set VENV_PATH environment variable or ensure virtual environment is created"
    exit 1
fi

if ! id "$APP_USER" &>/dev/null; then
    echo "Error: User does not exist: $APP_USER"
    echo "Set APP_USER environment variable or create the user first"
    exit 1
fi

# Validate executables exist
if [ ! -f "$VENV_PATH/bin/uvicorn" ]; then
    echo "Error: uvicorn not found at $VENV_PATH/bin/uvicorn"
    echo "Ensure virtual environment has uvicorn installed"
    exit 1
fi

if [ ! -f "$VENV_PATH/bin/celery" ]; then
    echo "Error: celery not found at $VENV_PATH/bin/celery"
    echo "Ensure virtual environment has celery installed"
    exit 1
fi

# Validate .env file exists
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Warning: .env file not found at $APP_DIR/.env"
    echo "Service will start but may fail without proper environment configuration"
fi

# Validate numeric parameters
if ! [[ "$API_PORT" =~ ^[0-9]+$ ]] || [ "$API_PORT" -lt 1 ] || [ "$API_PORT" -gt 65535 ]; then
    echo "Error: API_PORT must be a number between 1 and 65535, got: $API_PORT"
    exit 1
fi

if ! [[ "$API_WORKERS" =~ ^[0-9]+$ ]] || [ "$API_WORKERS" -lt 1 ]; then
    echo "Error: API_WORKERS must be a positive number, got: $API_WORKERS"
    exit 1
fi

if ! [[ "$CELERY_CONCURRENCY" =~ ^[0-9]+$ ]] || [ "$CELERY_CONCURRENCY" -lt 1 ]; then
    echo "Error: CELERY_CONCURRENCY must be a positive number, got: $CELERY_CONCURRENCY"
    exit 1
fi

if ! [[ "$FLOWER_PORT" =~ ^[0-9]+$ ]] || [ "$FLOWER_PORT" -lt 1 ] || [ "$FLOWER_PORT" -gt 65535 ]; then
    echo "Error: FLOWER_PORT must be a number between 1 and 65535, got: $FLOWER_PORT"
    exit 1
fi

if ! [[ "$REDIS_PORT" =~ ^[0-9]+$ ]] || [ "$REDIS_PORT" -lt 1 ] || [ "$REDIS_PORT" -gt 65535 ]; then
    echo "Error: REDIS_PORT must be a number between 1 and 65535, got: $REDIS_PORT"
    exit 1
fi

if ! [[ "$REDIS_DB" =~ ^[0-9]+$ ]] || [ "$REDIS_DB" -lt 0 ] || [ "$REDIS_DB" -gt 15 ]; then
    echo "Error: REDIS_DB must be a number between 0 and 15, got: $REDIS_DB"
    exit 1
fi

# Create application service
cat > /etc/systemd/system/marb2.0.service << EOF
[Unit]
Description=mARB 2.0 API Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/uvicorn app.main:app --host $API_HOST --port $API_PORT --workers $API_WORKERS
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create Celery worker service
cat > /etc/systemd/system/marb2.0-celery.service << EOF
[Unit]
Description=mARB 2.0 Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/celery -A app.services.queue.tasks worker --loglevel=info --concurrency=$CELERY_CONCURRENCY
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create Celery beat service (optional - for scheduled tasks)
cat > /etc/systemd/system/marb2.0-celery-beat.service << EOF
[Unit]
Description=mARB 2.0 Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/celery -A app.services.queue.tasks beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create Flower service (monitoring)
cat > /etc/systemd/system/marb2.0-flower.service << EOF
[Unit]
Description=mARB 2.0 Celery Flower (Monitoring)
After=network.target redis.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/celery -A app.services.queue.tasks flower --port=$FLOWER_PORT --broker=redis://$REDIS_HOST:$REDIS_PORT/$REDIS_DB
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set secure permissions on service files
if ! chmod 644 /etc/systemd/system/marb2.0.service 2>/dev/null; then
    echo "Error: Failed to set permissions on marb2.0.service"
    exit 1
fi

if ! chmod 644 /etc/systemd/system/marb2.0-celery.service 2>/dev/null; then
    echo "Error: Failed to set permissions on marb2.0-celery.service"
    exit 1
fi

if ! chmod 644 /etc/systemd/system/marb2.0-celery-beat.service 2>/dev/null; then
    echo "Error: Failed to set permissions on marb2.0-celery-beat.service"
    exit 1
fi

if ! chmod 644 /etc/systemd/system/marb2.0-flower.service 2>/dev/null; then
    echo "Error: Failed to set permissions on marb2.0-flower.service"
    exit 1
fi

if ! chown root:root /etc/systemd/system/marb2.0.service 2>/dev/null; then
    echo "Error: Failed to set ownership on marb2.0.service"
    exit 1
fi

if ! chown root:root /etc/systemd/system/marb2.0-celery.service 2>/dev/null; then
    echo "Error: Failed to set ownership on marb2.0-celery.service"
    exit 1
fi

if ! chown root:root /etc/systemd/system/marb2.0-celery-beat.service 2>/dev/null; then
    echo "Error: Failed to set ownership on marb2.0-celery-beat.service"
    exit 1
fi

if ! chown root:root /etc/systemd/system/marb2.0-flower.service 2>/dev/null; then
    echo "Error: Failed to set ownership on marb2.0-flower.service"
    exit 1
fi

echo "Systemd service files created with secure permissions!"
echo ""
echo "Configuration used:"
echo "  APP_DIR: $APP_DIR"
echo "  APP_USER: $APP_USER"
echo "  VENV_PATH: $VENV_PATH"
echo "  API_HOST: $API_HOST"
echo "  API_PORT: $API_PORT"
echo "  API_WORKERS: $API_WORKERS"
echo "  CELERY_CONCURRENCY: $CELERY_CONCURRENCY"
echo "  FLOWER_PORT: $FLOWER_PORT"
echo "  REDIS_HOST: $REDIS_HOST"
echo "  REDIS_PORT: $REDIS_PORT"
echo "  REDIS_DB: $REDIS_DB"
echo ""
echo "To enable and start services:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable marb2.0.service"
echo "  sudo systemctl enable marb2.0-celery.service"
echo "  sudo systemctl start marb2.0.service"
echo "  sudo systemctl start marb2.0-celery.service"
echo ""
echo "Optional services:"
echo "  sudo systemctl enable marb2.0-celery-beat.service  # For scheduled tasks"
echo "  sudo systemctl enable marb2.0-flower.service      # For Celery monitoring"
echo ""
echo "To customize configuration, set environment variables before running this script:"
echo "  export APP_DIR=/custom/path"
echo "  export API_PORT=9000"
echo "  # ... etc"

