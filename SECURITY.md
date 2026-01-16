# Security Guide for mARB 2.0

## Overview

This document outlines security best practices and configuration for mARB 2.0. Healthcare data (PHI) requires strict security measures to comply with HIPAA regulations.

## Quick Start

### 1. Generate Secure Keys

**Before deploying to production, generate secure keys:**

```bash
python generate_keys.py
```

This will output secure JWT and encryption keys. Copy these into your `.env` file.

### 2. Configure Environment Variables

Create a `.env` file from the template (see `.env.example` if available) and set:

- `JWT_SECRET_KEY` - Secure 32+ character key
- `ENCRYPTION_KEY` - Secure 32 character key
- `CORS_ORIGINS` - Your production domain(s)
- `REQUIRE_AUTH=true` - Enable authentication enforcement

### 3. Enable Authentication

Set `REQUIRE_AUTH=true` in your `.env` file to enforce authentication on all endpoints.

## Security Features

### 1. Rate Limiting

Rate limiting is enabled by default to prevent abuse:

- **Per minute**: 60 requests (configurable via `RATE_LIMIT_PER_MINUTE`)
- **Per hour**: 1000 requests (configurable via `RATE_LIMIT_PER_HOUR`)

Health check endpoints (`/api/v1/health`, `/`) are exempt from rate limiting.

**Rate limit headers** are included in responses:
- `X-RateLimit-Limit-Minute`: Maximum requests per minute
- `X-RateLimit-Remaining-Minute`: Remaining requests this minute
- `X-RateLimit-Limit-Hour`: Maximum requests per hour
- `X-RateLimit-Remaining-Hour`: Remaining requests this hour

When rate limit is exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

### 2. Authentication

JWT-based authentication is available but optional by default (for development).

**To enable authentication enforcement:**

1. Set `REQUIRE_AUTH=true` in `.env`
2. All endpoints except exempt paths will require a valid JWT token
3. Exempt paths (configurable via `AUTH_EXEMPT_PATHS`):
   - `/api/v1/health`
   - `/api/v1/docs`
   - `/api/v1/openapi.json`
   - `/`

**Using authentication:**

```bash
# Get access token (implement login endpoint)
TOKEN="your-jwt-token"

# Make authenticated request
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/claims
```

### 3. CORS Configuration

CORS is configured to restrict which origins can access the API. The configuration is environment-aware and automatically adjusts allowed methods and headers based on the `ENVIRONMENT` variable.

#### CORS Origins

The `CORS_ORIGINS` environment variable controls which domains can make cross-origin requests to the API. This is a comma-separated list of allowed origins.

**Development:**
```env
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

**Production:**
```env
ENVIRONMENT=production
CORS_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com
```

**Important Security Notes:**
- **Never use `*` for CORS origins in production** - Always specify exact domains
- **Never include `localhost` or `127.0.0.1` in production** - The application validates this and will fail to start if detected
- **All production origins must use HTTPS** - HTTP origins are rejected in production
- The application validates CORS configuration at startup and will refuse to start with insecure settings in production

#### CORS Methods (Environment-Aware)

The allowed HTTP methods differ between development and production:

**Development:**
- `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `HEAD`

**Production:**
- `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS` (HEAD is excluded for security)

#### CORS Headers (Environment-Aware)

The allowed request headers differ between development and production:

**Development:**
- `Content-Type`, `Authorization`, `Accept`, `X-Requested-With`, `X-API-Key`, and other common headers

**Production:**
- `Content-Type`, `Authorization`, `Accept`, `X-Requested-With`, `X-API-Key` (restricted set for security)

#### Configuration Validation

The application performs strict validation of CORS settings at startup:

- **Production checks:**
  - Rejects wildcard (`*`) origins
  - Rejects `localhost` or `127.0.0.1` origins
  - Rejects HTTP (non-HTTPS) origins
  - Validates origin format (must be valid URLs)

- **Development:**
  - More permissive settings allowed
  - `localhost` origins are permitted
  - HTTP origins are permitted

#### Troubleshooting CORS Issues

If you encounter CORS errors:

1. **Verify `CORS_ORIGINS` includes your frontend domain** - Check for typos
2. **Check protocol matches** - `http://` vs `https://` must match exactly
3. **Verify `ENVIRONMENT` variable** - Production has stricter validation
4. **Check browser console** - Look for specific CORS error messages
5. **Verify origin format** - Must be valid URLs (e.g., `https://app.example.com`, not `app.example.com`)

### 4. Audit Logging

All API requests are logged with:
- User ID (if authenticated)
- IP address
- Request method and path
- Response status code
- Request duration

This is required for HIPAA compliance to track PHI access.

### 5. Input Validation

All API endpoints use Pydantic models for input validation, preventing:
- SQL injection (via SQLAlchemy ORM)
- XSS attacks (via input sanitization)
- Invalid data types

## Production Security Checklist

Before deploying to production:

- [ ] Generate secure keys using `python generate_keys.py`
- [ ] Set `JWT_SECRET_KEY` to a secure 32+ character value
- [ ] Set `ENCRYPTION_KEY` to a secure 32 character value
- [ ] Set `REQUIRE_AUTH=true` to enforce authentication
- [ ] Configure `CORS_ORIGINS` with exact production domains (no wildcards)
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Use HTTPS/TLS (configure reverse proxy like nginx)
- [ ] Set up database SSL connections
- [ ] Configure Redis with authentication
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Review and test backup/restore procedures
- [ ] Document incident response procedures

## HTTPS/TLS Setup

**HTTPS/TLS is REQUIRED for production deployments** to protect PHI in transit and comply with HIPAA regulations.

### Option 1: nginx Reverse Proxy with Let's Encrypt (Recommended)

This is the recommended approach for production. nginx handles SSL termination and provides additional security features.

#### Step 1: Install Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

#### Step 2: Obtain SSL Certificate

```bash
# Replace api.yourdomain.com with your actual domain
sudo certbot --nginx -d api.yourdomain.com
```

Certbot will:
- Obtain SSL certificate from Let's Encrypt
- Automatically configure nginx
- Set up auto-renewal

#### Step 3: Configure nginx

Use the provided `deployment/nginx.conf.example` as a template:

```bash
# Copy template
sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/marb2.0

# Edit configuration
sudo nano /etc/nginx/sites-available/marb2.0
# Update: server_name, ssl_certificate paths (if not using Let's Encrypt)

# Enable site
sudo ln -s /etc/nginx/sites-available/marb2.0 /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

#### Step 4: Generate DH Parameters (Optional but Recommended)

For stronger security with DHE ciphers:

```bash
sudo openssl dhparam -out /etc/nginx/dhparam.pem 2048
```

Then uncomment `ssl_dhparam` in nginx configuration.

#### Step 5: Verify SSL Configuration

Test your SSL configuration:
- [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/) - Should achieve A+ rating
- Check certificate expiration: `sudo certbot certificates`
- Test auto-renewal: `sudo certbot renew --dry-run`

#### Step 6: Configure Auto-Renewal

Let's Encrypt certificates expire after 90 days. Certbot sets up auto-renewal automatically, but verify:

```bash
# Check renewal timer
sudo systemctl status certbot.timer

# Test renewal (dry run)
sudo certbot renew --dry-run
```

### Option 2: nginx with Custom SSL Certificates

If using your own SSL certificates:

1. Place certificates in secure locations:
   ```bash
   sudo mkdir -p /etc/ssl/certs /etc/ssl/private
   sudo cp your-certificate.crt /etc/ssl/certs/
   sudo cp your-private.key /etc/ssl/private/
   ```

2. Set proper permissions:
   ```bash
   sudo chmod 644 /etc/ssl/certs/your-certificate.crt
   sudo chmod 600 /etc/ssl/private/your-private.key
   ```

3. Update nginx configuration with certificate paths

### Option 3: FastAPI with SSL Directly (Not Recommended for Production)

While possible, this approach is not recommended because:
- No reverse proxy benefits (rate limiting, security headers, etc.)
- More complex certificate management
- Less flexible for scaling

If you must use this approach:

```python
# In run.py or startup script
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="/path/to/key.pem",
        ssl_certfile="/path/to/cert.pem",
    )
```

### SSL/TLS Security Best Practices

1. **Use Strong Cipher Suites**: The nginx config includes modern, secure ciphers
2. **Disable Old Protocols**: Only TLS 1.2 and 1.3 are enabled
3. **Enable HSTS**: Strict-Transport-Security header forces HTTPS
4. **OCSP Stapling**: Enabled in nginx config for faster SSL handshakes
5. **Regular Updates**: Keep nginx and certificates updated
6. **Monitor Expiration**: Set up alerts for certificate expiration

### Firewall Configuration

Ensure only necessary ports are open:

```bash
# Allow SSH (adjust port if changed)
sudo ufw allow 22/tcp

# Allow HTTP (for Let's Encrypt)
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Testing HTTPS Setup

1. **Verify HTTPS works**:
   ```bash
   curl -I https://api.yourdomain.com/api/v1/health
   ```

2. **Check SSL certificate**:
   ```bash
   openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com
   ```

3. **Test HTTP to HTTPS redirect**:
   ```bash
   curl -I http://api.yourdomain.com/api/v1/health
   # Should return 301 redirect to HTTPS
   ```

4. **Verify security headers**:
   ```bash
   curl -I https://api.yourdomain.com/api/v1/health
   # Check for Strict-Transport-Security, X-Frame-Options, etc.
   ```

## Database Security

### PostgreSQL SSL Connection

Update `DATABASE_URL` to use SSL:

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

### Redis Authentication

Enable Redis authentication:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-redis-password
```

Update Celery configuration to use Redis password:

```env
CELERY_BROKER_URL=redis://:password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:password@localhost:6379/0
```

## Environment Variables Security

**Never commit `.env` files to version control!**

The `.env` file should be:
- Added to `.gitignore`
- Stored securely (use secrets management in production)
- Restricted file permissions: `chmod 600 .env`

## Security Best Practices

### 1. Principle of Least Privilege

- Database users should have minimum required permissions
- API users should only access data they need
- Use role-based access control (RBAC) when implemented

### 2. Defense in Depth

- Multiple layers of security:
  - Network firewall
  - Application rate limiting
  - Authentication/authorization
  - Input validation
  - Database access controls

### 3. Regular Updates

- Keep dependencies updated: `pip list --outdated`
- Review security advisories
- Apply security patches promptly

### 4. Monitoring

- Monitor for suspicious activity
- Set up alerts for:
  - Failed authentication attempts
  - Rate limit violations
  - Unusual access patterns
  - Error rate spikes

### 5. Incident Response

- Document incident response procedures
- Have a plan for security breaches
- Regular security audits
- Penetration testing

## HIPAA Compliance

For HIPAA compliance, ensure:

1. **Access Controls**: Authentication and authorization
2. **Audit Logs**: All PHI access is logged
3. **Encryption**: Data encrypted at rest and in transit
4. **Data Minimization**: Only collect/store necessary PHI
5. **Business Associate Agreements**: Required for third-party services
6. **Security Policies**: Documented and enforced
7. **Training**: Staff trained on security procedures

See `samples/SECURITY_AND_HIPAA.md` for more detailed HIPAA guidance.

## Troubleshooting

### Rate Limit Issues

If you're hitting rate limits:
1. Check rate limit headers in responses
2. Adjust `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_PER_HOUR` if needed
3. Consider implementing per-user rate limits

### Authentication Issues

If authentication isn't working:
1. Verify `REQUIRE_AUTH=true` is set
2. Check JWT token is valid and not expired
3. Verify token is sent in `Authorization: Bearer <token>` header
4. Check exempt paths configuration

### CORS Issues

If CORS errors occur:
1. Verify `CORS_ORIGINS` includes your frontend domain
2. Check for typos in domain names
3. Ensure protocol matches (http vs https)
4. Check browser console for specific CORS error

## Additional Resources

- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)

