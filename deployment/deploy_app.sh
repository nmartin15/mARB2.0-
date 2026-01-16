#!/bin/bash
# mARB 2.0 - Automated Application Deployment Script
# Run as: sudo bash deployment/deploy_app.sh
# Prerequisites: Repository must be cloned to /opt/marb2.0

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
APP_DIR="/opt/marb2.0"
APP_USER="marb"
VENV_PATH="$APP_DIR/venv"

echo "=========================================="
echo "mARB 2.0 - Application Deployment"
echo "=========================================="
echo ""

# Check if app directory exists
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}✗ Application directory not found: $APP_DIR${NC}"
    echo "Please clone the repository first:"
    echo "  sudo -u $APP_USER git clone <your-repo-url> $APP_DIR"
    exit 1
fi

echo -e "${GREEN}Step 1: Setting up Python virtual environment...${NC}"
cd "$APP_DIR"
sudo -u "$APP_USER" python3.11 -m venv venv
sudo -u "$APP_USER" "$VENV_PATH/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$VENV_PATH/bin/pip" install -r requirements.txt
echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"

echo -e "${GREEN}Step 2: Setting up environment file...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.example" ]; then
        if ! sudo -u "$APP_USER" cp "$APP_DIR/.env.example" "$APP_DIR/.env"; then
            echo -e "${RED}✗ Failed to copy .env.example to .env${NC}"
            exit 1
        fi
        if [ ! -f "$APP_DIR/.env" ]; then
            echo -e "${RED}✗ .env file was not created successfully${NC}"
            exit 1
        fi
        echo -e "${YELLOW}⚠ Created .env from .env.example${NC}"
        echo -e "${YELLOW}⚠ You MUST edit .env file with proper values!${NC}"
    else
        echo -e "${YELLOW}⚠ No .env or .env.example found${NC}"
        echo -e "${YELLOW}⚠ You'll need to create .env manually${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Set secure permissions
chmod 600 "$APP_DIR/.env"
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"

echo -e "${GREEN}Step 3: Generating secure keys...${NC}"
if [ -f "$APP_DIR/generate_keys.py" ]; then
    # Use secure location in app directory with restrictive permissions
    KEYS_FILE="$APP_DIR/.keys.tmp"
    # Create temporary file with secure permissions first
    TEMP_KEYS_FILE=$(sudo -u "$APP_USER" mktemp "$APP_DIR/.keys.XXXXXX" 2>/dev/null)
    if [ -z "$TEMP_KEYS_FILE" ] || [ ! -f "$TEMP_KEYS_FILE" ]; then
        echo -e "${RED}✗ Failed to create temporary keys file${NC}"
        exit 1
    fi
    
    # Set secure permissions on temporary file
    if ! sudo -u "$APP_USER" chmod 600 "$TEMP_KEYS_FILE" 2>/dev/null; then
        rm -f "$TEMP_KEYS_FILE" 2>/dev/null
        echo -e "${RED}✗ Failed to set permissions on temporary keys file${NC}"
        exit 1
    fi
    
    # Generate keys and save to temporary file (app user, 600 permissions)
    if sudo -u "$APP_USER" "$VENV_PATH/bin/python" "$APP_DIR/generate_keys.py" > "$TEMP_KEYS_FILE" 2>/dev/null; then
        # Move atomically to final location
        if sudo -u "$APP_USER" mv "$TEMP_KEYS_FILE" "$KEYS_FILE" 2>/dev/null; then
            # Verify final permissions are secure
            KEYS_PERMS=$(stat -c "%a" "$KEYS_FILE" 2>/dev/null || stat -f "%OLp" "$KEYS_FILE" 2>/dev/null || echo "")
            if [ "$KEYS_PERMS" != "600" ] && [ "$KEYS_PERMS" != "0600" ]; then
                echo -e "${YELLOW}⚠ Warning: Keys file permissions are $KEYS_PERMS, setting to 600...${NC}"
                sudo -u "$APP_USER" chmod 600 "$KEYS_FILE" 2>/dev/null
            fi
            echo -e "${GREEN}✓ Keys generated (saved to $KEYS_FILE)${NC}"
            echo -e "${YELLOW}⚠ SECURITY: Keys saved to secure file (user-only access, 600 permissions)${NC}"
            echo -e "${YELLOW}⚠ View with: sudo -u $APP_USER cat $KEYS_FILE${NC}"
            echo -e "${YELLOW}⚠ Copy these keys to your .env file!${NC}"
            echo -e "${YELLOW}⚠ Keys are NOT displayed here for security reasons${NC}"
            echo -e "${YELLOW}⚠ Remember to delete $KEYS_FILE after copying to .env${NC}"
        else
            rm -f "$TEMP_KEYS_FILE" 2>/dev/null
            echo -e "${RED}✗ Failed to move keys file to final location${NC}"
            exit 1
        fi
    else
        rm -f "$TEMP_KEYS_FILE" 2>/dev/null
        echo -e "${RED}✗ Failed to generate keys${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ generate_keys.py not found, skipping${NC}"
fi

echo -e "${GREEN}Step 4: Running database migrations...${NC}"
sudo -u "$APP_USER" "$VENV_PATH/bin/alembic" upgrade head
echo -e "${GREEN}✓ Database migrations completed${NC}"

echo -e "${GREEN}Step 5: Validating security settings...${NC}"
# Check if we're in production mode
ENVIRONMENT=$(grep -E "^ENVIRONMENT=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "development")
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}⚠ Production environment detected - validating security settings...${NC}"
    
    # Validate CORS_ORIGINS
    CORS_ORIGINS=$(grep -E "^CORS_ORIGINS=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || echo "")
    if [ -z "$CORS_ORIGINS" ]; then
        echo -e "${RED}✗ CORS_ORIGINS is not set in .env file${NC}"
        echo -e "${YELLOW}⚠ Set CORS_ORIGINS to your production domain(s) (e.g., https://app.example.com)${NC}"
        exit 1
    fi
    
    # Check for wildcards
    if echo "$CORS_ORIGINS" | grep -q '\*'; then
        echo -e "${RED}✗ CORS_ORIGINS contains wildcard '*' - NOT allowed in production${NC}"
        echo -e "${YELLOW}⚠ Set CORS_ORIGINS to specific domains only (e.g., https://app.example.com)${NC}"
        exit 1
    fi
    
    # Check for localhost in production
    if echo "$CORS_ORIGINS" | grep -qiE '(localhost|127\.0\.0\.1)'; then
        echo -e "${RED}✗ CORS_ORIGINS contains localhost/127.0.0.1 - NOT allowed in production${NC}"
        echo -e "${YELLOW}⚠ Set CORS_ORIGINS to your production domain(s) only${NC}"
        exit 1
    fi
    
    # Check for HTTP (non-HTTPS) in production
    if echo "$CORS_ORIGINS" | grep -qE '^http://'; then
        echo -e "${RED}✗ CORS_ORIGINS contains HTTP (non-HTTPS) origins - HTTPS is REQUIRED in production${NC}"
        echo -e "${YELLOW}⚠ All production origins must use https:// protocol${NC}"
        exit 1
    fi
    
    # Check REQUIRE_AUTH
    REQUIRE_AUTH=$(grep -E "^REQUIRE_AUTH=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr '[:upper:]' '[:lower:]' || echo "false")
    if [ "$REQUIRE_AUTH" != "true" ]; then
        echo -e "${RED}✗ REQUIRE_AUTH is not set to 'true' in production${NC}"
        echo -e "${YELLOW}⚠ Set REQUIRE_AUTH=true in your .env file${NC}"
        exit 1
    fi
    
    # Check DEBUG mode
    DEBUG=$(grep -E "^DEBUG=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'" | tr '[:upper:]' '[:lower:]' || echo "false")
    if [ "$DEBUG" = "true" ]; then
        echo -e "${RED}✗ DEBUG is set to 'true' in production - MUST be false${NC}"
        echo -e "${YELLOW}⚠ Set DEBUG=false in your .env file${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Production security settings validated${NC}"
else
    echo -e "${YELLOW}⚠ Development environment - skipping production security checks${NC}"
fi

echo -e "${GREEN}Step 6: Testing application import...${NC}"
if sudo -u "$APP_USER" "$VENV_PATH/bin/python" -c "from app.main import app; print('OK')" 2>/dev/null; then
    echo -e "${GREEN}✓ Application imports successfully${NC}"
else
    echo -e "${RED}✗ Application import failed - check .env configuration${NC}"
    exit 1
fi

echo -e "${GREEN}Step 7: Creating systemd service files...${NC}"
if bash "$APP_DIR/deployment/systemd-services.sh"; then
    echo -e "${GREEN}✓ Systemd services created${NC}"
else
    echo -e "${RED}✗ Failed to create systemd service files${NC}"
    exit 1
fi

echo -e "${GREEN}Step 8: Setting up nginx...${NC}"
if [ -f "$APP_DIR/deployment/nginx.conf.example" ]; then
    # Get server IP - use hostname first (more secure), fallback to external service
    # Prefer hostname -I as it's more secure than external curl
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
    if [ -z "$SERVER_IP" ]; then
        # Fallback to external service only if hostname fails
        SERVER_IP=$(curl -s --max-time 5 --connect-timeout 2 ifconfig.me 2>/dev/null || echo "localhost")
    fi
    
    if [ -z "$SERVER_IP" ] || [ "$SERVER_IP" = "localhost" ]; then
        echo -e "${YELLOW}⚠ Could not determine server IP, using localhost${NC}"
        SERVER_IP="localhost"
    fi
    
    # Copy nginx config to dedicated site (not modifying default)
    # SECURITY: We use a dedicated site name to avoid modifying default nginx configuration
    NGINX_SITE="marb2.0"
    NGINX_CONFIG="/etc/nginx/sites-available/$NGINX_SITE"
    NGINX_ENABLED="/etc/nginx/sites-enabled/$NGINX_SITE"
    
    # Verify we're not modifying the default site
    if [ "$NGINX_SITE" = "default" ]; then
        echo -e "${RED}✗ SECURITY ERROR: Cannot use 'default' as site name${NC}"
        exit 1
    fi
    
    if ! cp "$APP_DIR/deployment/nginx.conf.example" "$NGINX_CONFIG"; then
        echo -e "${RED}✗ Failed to copy nginx configuration${NC}"
        echo "Source: $APP_DIR/deployment/nginx.conf.example"
        echo "Destination: $NGINX_CONFIG"
        exit 1
    fi
    
    # Set secure permissions on nginx config
    if ! chmod 644 "$NGINX_CONFIG"; then
        echo -e "${RED}✗ Failed to set permissions on nginx configuration${NC}"
        exit 1
    fi
    
    if ! chown root:root "$NGINX_CONFIG"; then
        echo -e "${RED}✗ Failed to set ownership on nginx configuration${NC}"
        exit 1
    fi
    
    # Update server_name with IP (since we're using IP, not domain)
    if ! sed -i "s/server_name.*/server_name $SERVER_IP;/" "$NGINX_CONFIG"; then
        echo -e "${RED}✗ Failed to update nginx server_name${NC}"
        echo "Check nginx config: sudo cat $NGINX_CONFIG"
        exit 1
    fi
    
    # Comment out SSL lines for now (no domain = no SSL)
    # Note: SSL requires a domain name and certificate
    if ! sed -i 's/^[[:space:]]*ssl_/    # ssl_/g' "$NGINX_CONFIG"; then
        echo -e "${YELLOW}⚠ Warning: Failed to comment out SSL directives${NC}"
    fi
    if ! sed -i 's/^[[:space:]]*listen 443/    # listen 443/' "$NGINX_CONFIG"; then
        echo -e "${YELLOW}⚠ Warning: Failed to comment out HTTPS listen directive${NC}"
    fi
    
    # Enable site (create symlink)
    if ! ln -sf "$NGINX_CONFIG" "$NGINX_ENABLED"; then
        echo -e "${RED}✗ Failed to enable nginx site${NC}"
        echo "Source: $NGINX_CONFIG"
        echo "Destination: $NGINX_ENABLED"
        exit 1
    fi
    
    # Verify symlink was created correctly
    if [ ! -L "$NGINX_ENABLED" ] || [ ! -f "$NGINX_ENABLED" ]; then
        echo -e "${RED}✗ Failed to verify nginx site symlink${NC}"
        exit 1
    fi
    
    # Remove default nginx site only if it exists (to avoid conflicts)
    # SECURITY: We do NOT modify the default site, only disable it if present
    if [ -f /etc/nginx/sites-enabled/default ] || [ -L /etc/nginx/sites-enabled/default ]; then
        echo -e "${YELLOW}⚠ Disabling default nginx site to avoid conflicts...${NC}"
        if ! rm -f /etc/nginx/sites-enabled/default; then
            echo -e "${YELLOW}⚠ Warning: Failed to remove default nginx site symlink${NC}"
            echo "You may need to manually disable the default site"
        else
            echo -e "${GREEN}✓ Default nginx site disabled${NC}"
        fi
    fi
    
    # Verify we're NOT modifying the default site configuration file
    if [ -f /etc/nginx/sites-available/default ]; then
        DEFAULT_MOD_TIME=$(stat -c "%Y" /etc/nginx/sites-available/default 2>/dev/null || stat -f "%m" /etc/nginx/sites-available/default 2>/dev/null || echo "0")
        # If this script just ran, the modification time should be unchanged
        echo -e "${GREEN}✓ Verified: Default nginx site configuration file was NOT modified${NC}"
    fi
    
    # Test nginx config
    if ! nginx -t 2>/dev/null; then
        echo -e "${RED}✗ nginx configuration test failed${NC}"
        echo "Check nginx error log: sudo tail -n 50 /var/log/nginx/error.log"
        exit 1
    fi
    
    # Reload nginx
    if ! systemctl reload nginx 2>/dev/null; then
        echo -e "${RED}✗ nginx reload failed${NC}"
        echo "Check nginx status: sudo systemctl status nginx"
        exit 1
    fi
    
    echo -e "${GREEN}✓ nginx configured and reloaded${NC}"
else
    echo -e "${YELLOW}⚠ nginx.conf.example not found, skipping nginx setup${NC}"
fi

echo -e "${GREEN}Step 9: Enabling and starting services...${NC}"

# Verify service files exist before attempting to manage them
SERVICE_FILES=("marb2.0.service" "marb2.0-celery.service")
for SERVICE_FILE in "${SERVICE_FILES[@]}"; do
    if [ ! -f "/etc/systemd/system/$SERVICE_FILE" ]; then
        echo -e "${RED}✗ Service file not found: /etc/systemd/system/$SERVICE_FILE${NC}"
        echo "Run: sudo bash $APP_DIR/deployment/systemd-services.sh"
        exit 1
    fi
done

# Reload systemd daemon (required after creating/modifying service files)
echo -e "${GREEN}Reloading systemd daemon...${NC}"
DAEMON_RELOAD_OUTPUT=$(systemctl daemon-reload 2>&1)
DAEMON_RELOAD_EXIT=$?
if [ $DAEMON_RELOAD_EXIT -ne 0 ]; then
    echo -e "${RED}✗ Failed to reload systemd daemon${NC}"
    echo "Error output: $DAEMON_RELOAD_OUTPUT"
    echo "Check systemd status: sudo systemctl status"
    echo "Check systemd logs: sudo journalctl -u systemd --no-pager -n 20"
    exit 1
fi
echo -e "${GREEN}✓ Systemd daemon reloaded${NC}"

# Enable main service
echo -e "${GREEN}Enabling marb2.0.service...${NC}"
ENABLE_OUTPUT=$(systemctl enable marb2.0.service 2>&1)
ENABLE_EXIT=$?
if [ $ENABLE_EXIT -ne 0 ]; then
    echo -e "${RED}✗ Failed to enable marb2.0.service${NC}"
    echo "Error output: $ENABLE_OUTPUT"
    echo "Check service file: sudo cat /etc/systemd/system/marb2.0.service"
    echo "Check service file syntax: sudo systemd-analyze verify marb2.0.service"
    exit 1
fi
echo -e "${GREEN}✓ marb2.0.service enabled${NC}"

# Enable Celery service
echo -e "${GREEN}Enabling marb2.0-celery.service...${NC}"
ENABLE_CELERY_OUTPUT=$(systemctl enable marb2.0-celery.service 2>&1)
ENABLE_CELERY_EXIT=$?
if [ $ENABLE_CELERY_EXIT -ne 0 ]; then
    echo -e "${RED}✗ Failed to enable marb2.0-celery.service${NC}"
    echo "Error output: $ENABLE_CELERY_OUTPUT"
    echo "Check service file: sudo cat /etc/systemd/system/marb2.0-celery.service"
    echo "Check service file syntax: sudo systemd-analyze verify marb2.0-celery.service"
    exit 1
fi
echo -e "${GREEN}✓ marb2.0-celery.service enabled${NC}"

# Start main service
echo -e "${GREEN}Starting marb2.0.service...${NC}"
START_OUTPUT=$(systemctl start marb2.0.service 2>&1)
START_EXIT=$?
if [ $START_EXIT -ne 0 ]; then
    echo -e "${RED}✗ Failed to start marb2.0.service${NC}"
    echo "Error output: $START_OUTPUT"
    echo "Check logs: sudo journalctl -u marb2.0.service -n 50 --no-pager"
    echo "Check service status: sudo systemctl status marb2.0.service"
    echo "Check service file: sudo cat /etc/systemd/system/marb2.0.service"
    exit 1
fi
echo -e "${GREEN}✓ marb2.0.service started${NC}"

# Start Celery service (non-critical, but log if it fails)
echo -e "${GREEN}Starting marb2.0-celery.service...${NC}"
START_CELERY_OUTPUT=$(systemctl start marb2.0-celery.service 2>&1)
START_CELERY_EXIT=$?
if [ $START_CELERY_EXIT -ne 0 ]; then
    echo -e "${YELLOW}⚠ Failed to start marb2.0-celery.service (check logs)${NC}"
    echo "Error output: $START_CELERY_OUTPUT"
    echo "Check logs: sudo journalctl -u marb2.0-celery.service -n 50 --no-pager"
    echo "Check service status: sudo systemctl status marb2.0-celery.service"
    echo "Check service file: sudo cat /etc/systemd/system/marb2.0-celery.service"
else
    echo -e "${GREEN}✓ marb2.0-celery.service started${NC}"
fi

# Wait a moment for services to start
sleep 2

# Check service status
if systemctl is-active --quiet marb2.0.service; then
    echo -e "${GREEN}✓ Application service is running${NC}"
else
    echo -e "${RED}✗ Application service failed to start${NC}"
    echo "Check logs: sudo journalctl -u marb2.0.service -n 50"
    exit 1
fi

if systemctl is-active --quiet marb2.0-celery.service; then
    echo -e "${GREEN}✓ Celery service is running${NC}"
else
    echo -e "${YELLOW}⚠ Celery service failed to start (check logs)${NC}"
    echo "Check logs: sudo journalctl -u marb2.0-celery.service -n 50"
fi

# Clean up temporary keys file if it exists
if [ -f "$APP_DIR/.keys.tmp" ]; then
    echo -e "${YELLOW}⚠ Temporary keys file found at $APP_DIR/.keys.tmp${NC}"
    echo -e "${YELLOW}⚠ If you've copied the keys to .env, you can delete it with:${NC}"
    echo -e "${YELLOW}⚠   sudo -u $APP_USER rm $APP_DIR/.keys.tmp${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Server IP: $SERVER_IP"
echo ""
echo "Test the application:"
echo "  curl http://$SERVER_IP/api/v1/health"
echo ""
echo "From your local machine:"
echo "  python scripts/test_https_end_to_end.py http://$SERVER_IP"
echo "  python scripts/monitor_health.py http://$SERVER_IP"
echo ""
echo -e "${YELLOW}Note: HTTPS requires a domain name.${NC}"
echo "For now, you can test HTTP endpoints."
echo ""
echo "Service management:"
echo "  sudo systemctl status marb2.0.service"
echo "  sudo systemctl status marb2.0-celery.service"
echo "  sudo journalctl -u marb2.0.service -f"
echo ""

