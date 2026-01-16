# HTTPS/TLS Setup Guide for mARB 2.0

This guide provides step-by-step instructions for setting up HTTPS/TLS for mARB 2.0 in production.

## Prerequisites

- Ubuntu 20.04+ or similar Linux distribution
- Domain name pointing to your server
- nginx installed
- Ports 80 and 443 open in firewall

## Quick Start: Let's Encrypt with nginx

### 1. Install Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Configure nginx (Basic HTTP First)

Before obtaining SSL certificate, configure nginx for HTTP:

```bash
# Copy template
sudo cp /opt/marb2.0/deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0

# Edit and update server_name
sudo nano /etc/nginx/sites-available/marb2.0
# Change: server_name api.yourdomain.com; (replace with your domain)

# Temporarily comment out SSL lines for initial setup
# Enable site
sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Obtain SSL Certificate

```bash
# Replace api.yourdomain.com with your actual domain
sudo certbot --nginx -d api.yourdomain.com
```

Certbot will:
- Prompt for email (for renewal notifications)
- Ask to agree to terms of service
- Optionally share email with EFF
- Automatically configure nginx with SSL
- Set up auto-renewal

### 4. Verify Certificate

```bash
# Check certificate status
sudo certbot certificates

# Test auto-renewal
sudo certbot renew --dry-run
```

### 5. Update nginx Configuration

After Certbot configures basic SSL, enhance security by using the full configuration from `nginx.conf.example`:

```bash
# Backup Certbot's configuration
sudo cp /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-available/marb2.0.certbot-backup

# Copy enhanced configuration
sudo cp /opt/marb2.0/deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0

# Update with your domain and Let's Encrypt certificate paths
# Let's Encrypt certificates are typically at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem

sudo nano /etc/nginx/sites-available/marb2.0
```

Update these lines:
```nginx
server_name api.yourdomain.com;  # Your domain

ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

### 6. Generate DH Parameters (Recommended)

For stronger security with DHE ciphers:

```bash
sudo openssl dhparam -out /etc/nginx/dhparam.pem 2048
# This may take a few minutes
```

Then uncomment in nginx config:
```nginx
ssl_dhparam /etc/nginx/dhparam.pem;
```

### 7. Configure OCSP Stapling

If using Let's Encrypt, add to nginx config:

```nginx
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/letsencrypt/live/yourdomain.com/chain.pem;
```

### 8. Test and Reload

```bash
# Test configuration
sudo nginx -t

# If test passes, reload
sudo systemctl reload nginx
```

## Manual Certificate Setup

If you have your own SSL certificates:

### 1. Place Certificates

```bash
# Create directories
sudo mkdir -p /etc/ssl/certs /etc/ssl/private

# Copy certificates
sudo cp your-certificate.crt /etc/ssl/certs/yourdomain.com.crt
sudo cp your-private.key /etc/ssl/private/yourdomain.com.key

# Set permissions
sudo chmod 644 /etc/ssl/certs/yourdomain.com.crt
sudo chmod 600 /etc/ssl/private/yourdomain.com.key
```

### 2. Configure nginx

Update `nginx.conf.example` with your certificate paths:

```nginx
ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
```

## Verify HTTPS Setup

### 1. Test HTTPS Connection

```bash
curl -I https://api.yourdomain.com/api/v1/health
```

Should return HTTP 200 with security headers.

### 2. Test HTTP to HTTPS Redirect

```bash
curl -I http://api.yourdomain.com/api/v1/health
```

Should return HTTP 301 redirect to HTTPS.

### 3. Check SSL Certificate

```bash
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com < /dev/null
```

### 4. Test SSL Rating

Visit [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/) and enter your domain. Should achieve **A+ rating** with the provided configuration.

### 5. Verify Security Headers

```bash
curl -I https://api.yourdomain.com/api/v1/health | grep -i "strict-transport\|x-frame\|x-content"
```

Should see:
- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `X-XSS-Protection`

## Auto-Renewal Setup

Let's Encrypt certificates expire after 90 days. Certbot sets up auto-renewal automatically.

### Verify Auto-Renewal

```bash
# Check timer status
sudo systemctl status certbot.timer

# Check renewal schedule
sudo systemctl list-timers | grep certbot

# Test renewal (dry run)
sudo certbot renew --dry-run
```

### Manual Renewal

If needed, renew manually:

```bash
sudo certbot renew
sudo systemctl reload nginx
```

## Troubleshooting

### Certificate Not Obtained

1. **Check DNS**: Ensure domain points to your server
   ```bash
   dig api.yourdomain.com
   ```

2. **Check Port 80**: Must be open for Let's Encrypt validation
   ```bash
   sudo ufw allow 80/tcp
   ```

3. **Check nginx**: Must be running and accessible
   ```bash
   sudo systemctl status nginx
   curl http://api.yourdomain.com
   ```

### SSL Handshake Errors

1. **Check certificate paths**: Verify files exist
   ```bash
   sudo ls -la /etc/letsencrypt/live/yourdomain.com/
   ```

2. **Check permissions**: Certificates must be readable
   ```bash
   sudo chmod 644 /etc/letsencrypt/live/yourdomain.com/fullchain.pem
   sudo chmod 600 /etc/letsencrypt/live/yourdomain.com/privkey.pem
   ```

3. **Check nginx error logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Mixed Content Warnings

If your frontend shows mixed content warnings:
- Ensure all API calls use `https://`
- Check CORS configuration allows HTTPS origins
- Verify `X-Forwarded-Proto` header is set correctly

## Security Checklist

After setup, verify:

- [ ] HTTPS is working (test in browser)
- [ ] HTTP redirects to HTTPS
- [ ] SSL certificate is valid (not expired)
- [ ] SSL Labs rating is A or A+
- [ ] Security headers are present
- [ ] Auto-renewal is configured
- [ ] Firewall only allows 22, 80, 443
- [ ] nginx configuration tested (`nginx -t`)
- [ ] Application accessible via HTTPS

## Additional Resources

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot User Guide](https://certbot.eff.org/docs/)
- [nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/)

