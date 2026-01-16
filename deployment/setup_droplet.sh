#!/bin/bash
# mARB 2.0 - Automated Droplet Setup Script
# This script sets up a fresh Ubuntu droplet for mARB 2.0 staging
# Run as: sudo bash deployment/setup_droplet.sh

set -e  # Exit on error

echo "=========================================="
echo "mARB 2.0 - Droplet Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/marb2.0"
APP_USER="marb"
DB_NAME="marb_risk_engine"
DB_USER="marb_user"

echo -e "${GREEN}Step 1: Updating system packages...${NC}"
apt update && apt upgrade -y

echo -e "${GREEN}Step 2: Installing system dependencies...${NC}"
apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    certbot \
    python3-certbot-nginx \
    ufw \
    curl \
    wget

echo -e "${GREEN}Step 3: Creating application user...${NC}"
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG sudo "$APP_USER"
    echo -e "${GREEN}✓ User '$APP_USER' created${NC}"
else
    echo -e "${YELLOW}⚠ User '$APP_USER' already exists${NC}"
fi

echo -e "${GREEN}Step 4: Configuring firewall...${NC}"
ufw --force enable
ufw allow OpenSSH
ufw allow 'Nginx Full'
# Explicitly deny Redis port from external access (Redis should only be accessible locally)
ufw deny 6379/tcp
ufw status

echo -e "${GREEN}Step 5: Setting up PostgreSQL...${NC}"
# Generate secure password for database user
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
# Save password to secure file (root-only, 600 permissions)
PASSWORD_FILE="/root/marb_passwords.txt"
# Use a temporary file first, then move atomically to prevent race conditions
TEMP_PASSWORD_FILE=$(mktemp /tmp/marb_passwords.XXXXXX)
chmod 600 "$TEMP_PASSWORD_FILE"
chown root:root "$TEMP_PASSWORD_FILE"
if echo "Database Password: $DB_PASSWORD" > "$TEMP_PASSWORD_FILE" 2>/dev/null; then
    mv "$TEMP_PASSWORD_FILE" "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    chown root:root "$PASSWORD_FILE"
    echo -e "${GREEN}✓ Database password generated and saved securely${NC}"
    echo -e "${YELLOW}⚠ SECURITY: Password saved to $PASSWORD_FILE (root-only access)${NC}"
    echo -e "${YELLOW}⚠ View with: sudo cat $PASSWORD_FILE${NC}"
    echo -e "${YELLOW}⚠ SAVE THIS PASSWORD - You'll need it for .env file!${NC}"
    echo -e "${YELLOW}⚠ Password is NOT displayed here for security reasons${NC}"
else
    rm -f "$TEMP_PASSWORD_FILE" 2>/dev/null
    echo -e "${RED}✗ Failed to save database password${NC}"
    exit 1
fi

# Create database and user
# Connect as postgres superuser (uses peer authentication, no password needed)
# Password is embedded in SQL heredoc (in memory, not command line) - secure for one-time setup
sudo -u postgres psql <<EOF
-- Create database if it doesn't exist
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Create user if it doesn't exist, otherwise alter the user's password
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    ELSE
        ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
\q
EOF

# Clear password from shell environment to prevent exposure in process list
# Note: Password was only in heredoc (script memory), never in command line or environment
DB_PASSWORD=""

echo -e "${GREEN}✓ PostgreSQL database and user created${NC}"

echo -e "${GREEN}Step 6: Setting up Redis...${NC}"
# Generate secure password for Redis
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
# Save password to secure file (append to existing password file)
# Use temporary file and append atomically
TEMP_REDIS_PASS=$(mktemp /tmp/marb_redis_pass.XXXXXX)
chmod 600 "$TEMP_REDIS_PASS"
chown root:root "$TEMP_REDIS_PASS"
if echo "Redis Password: $REDIS_PASSWORD" > "$TEMP_REDIS_PASS" 2>/dev/null; then
    cat "$TEMP_REDIS_PASS" >> "$PASSWORD_FILE"
    rm -f "$TEMP_REDIS_PASS"
    # Ensure file permissions are still secure
    chmod 600 "$PASSWORD_FILE"
    chown root:root "$PASSWORD_FILE"
    echo -e "${GREEN}✓ Redis password generated and saved securely${NC}"
    echo -e "${YELLOW}⚠ SECURITY: Password saved to $PASSWORD_FILE (root-only access)${NC}"
    echo -e "${YELLOW}⚠ View with: sudo cat $PASSWORD_FILE${NC}"
    echo -e "${YELLOW}⚠ SAVE THIS PASSWORD - You'll need it for .env file!${NC}"
    echo -e "${YELLOW}⚠ Password is NOT displayed here for security reasons${NC}"
else
    rm -f "$TEMP_REDIS_PASS" 2>/dev/null
    echo -e "${RED}✗ Failed to save Redis password${NC}"
    exit 1
fi

# Configure Redis
if ! grep -q "^requirepass" /etc/redis/redis.conf; then
    echo "requirepass $REDIS_PASSWORD" >> /etc/redis/redis.conf
else
    sed -i "s/^requirepass.*/requirepass $REDIS_PASSWORD/" /etc/redis/redis.conf
fi

# Secure Redis: bind to localhost only
# Backup original config
cp /etc/redis/redis.conf /etc/redis/redis.conf.backup

# Comment out any existing bind directives (active or commented)
sed -i 's/^[[:space:]]*bind .*/# & (replaced with bind 127.0.0.1 below)/' /etc/redis/redis.conf
sed -i 's/^# bind .*/# & (replaced with bind 127.0.0.1 below)/' /etc/redis/redis.conf

# Add bind to 127.0.0.1 in the network section
# Find the network section (usually has "# Network" or "# bind" comments)
if grep -q "^# Network" /etc/redis/redis.conf; then
    # Insert after "# Network" comment
    sed -i '/^# Network/a bind 127.0.0.1' /etc/redis/redis.conf
elif grep -q "^# bind" /etc/redis/redis.conf; then
    # Insert after first "# bind" comment
    sed -i '0,/^# bind/a bind 127.0.0.1' /etc/redis/redis.conf
else
    # Fallback: add after port directive
    sed -i '/^port /a bind 127.0.0.1' /etc/redis/redis.conf
fi

# Ensure protected-mode is enabled (default, but make it explicit)
sed -i 's/^#*[[:space:]]*protected-mode.*/protected-mode yes/' /etc/redis/redis.conf
if ! grep -q "^protected-mode" /etc/redis/redis.conf; then
    sed -i '/^bind 127.0.0.1/a protected-mode yes' /etc/redis/redis.conf
fi

# Disable dangerous commands
if ! grep -q "^rename-command FLUSHDB" /etc/redis/redis.conf; then
    echo "" >> /etc/redis/redis.conf
    echo "# Security: disable dangerous commands" >> /etc/redis/redis.conf
    echo "rename-command FLUSHDB \"\"" >> /etc/redis/redis.conf
    echo "rename-command FLUSHALL \"\"" >> /etc/redis/redis.conf
    echo "rename-command CONFIG \"\"" >> /etc/redis/redis.conf
fi

# Restart Redis
if ! systemctl restart redis-server 2>/dev/null; then
    echo -e "${RED}✗ Failed to restart Redis${NC}"
    echo "Check Redis status: sudo systemctl status redis-server"
    exit 1
fi

if ! systemctl enable redis-server 2>/dev/null; then
    echo -e "${RED}✗ Failed to enable Redis${NC}"
    exit 1
fi

# Verify Redis is bound to localhost only
REDIS_BIND=$(grep "^bind " /etc/redis/redis.conf | tail -1 | awk '{print $2}')
if [ "$REDIS_BIND" = "127.0.0.1" ]; then
    echo -e "${GREEN}✓ Redis bound to localhost (127.0.0.1)${NC}"
else
    echo -e "${RED}✗ Warning: Redis bind configuration may not be correct${NC}"
fi

# Test Redis connection
# Use REDISCLI_AUTH environment variable (only set for this command invocation)
# This avoids command-line exposure but is acceptable for a one-time setup script
if REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -h 127.0.0.1 ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis configured and tested${NC}"
else
    echo -e "${RED}✗ Warning: Redis connection test failed${NC}"
    echo -e "${YELLOW}⚠ Verify Redis is running: sudo systemctl status redis-server${NC}"
fi

# Clear password from shell environment to prevent exposure in process list
REDIS_PASSWORD=""

# Verify Redis is not accessible from external interfaces
# Double-check binding configuration
REDIS_BIND_CHECK=$(grep "^bind " /etc/redis/redis.conf | tail -1 | awk '{print $2}')
if [ "$REDIS_BIND_CHECK" != "127.0.0.1" ]; then
    echo -e "${RED}✗ CRITICAL: Redis is not bound to localhost only!${NC}"
    echo -e "${RED}✗ Current bind: $REDIS_BIND_CHECK${NC}"
    exit 1
fi

# Verify protected mode
if ! grep -q "^protected-mode yes" /etc/redis/redis.conf; then
    echo -e "${RED}✗ CRITICAL: Redis protected mode is not enabled!${NC}"
    exit 1
fi

# Verify password is set
if ! grep -q "^requirepass" /etc/redis/redis.conf; then
    echo -e "${RED}✗ CRITICAL: Redis password is not set!${NC}"
    exit 1
fi

# Verify firewall is blocking Redis port
if ! ufw status | grep -q "6379.*DENY"; then
    echo -e "${YELLOW}⚠ Warning: Firewall rule for Redis port 6379 not found${NC}"
    echo -e "${YELLOW}⚠ Adding firewall rule to deny external access to Redis...${NC}"
    ufw deny 6379/tcp
fi

echo -e "${GREEN}✓ Redis security: bound to localhost, password protected, firewall configured${NC}"

echo -e "${GREEN}Step 7: Creating application directory...${NC}"
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo -e "${YELLOW}IMPORTANT - Passwords saved to: $PASSWORD_FILE${NC}"
echo -e "${YELLOW}View with: sudo cat $PASSWORD_FILE${NC}"
echo ""
echo "Next steps:"
echo "  1. Clone your repository to $APP_DIR"
echo "  2. Run: sudo bash deployment/deploy_app.sh"
echo "  3. Configure .env file with the passwords above"
echo ""
echo "To clone repository:"
echo "  sudo -u $APP_USER git clone <your-repo-url> $APP_DIR"
echo ""

