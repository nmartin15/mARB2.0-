# CORS Configuration Documentation

**Last Updated:** 2025-12-26  
**Status:** ✅ Complete - Production validation enforced

## Overview

CORS (Cross-Origin Resource Sharing) configuration is environment-aware and automatically enforces security best practices in production. The application will **refuse to start** in production with insecure CORS settings.

## Development vs Production Behavior

### Development Environment

**Default Behavior:**
- Defaults to `http://localhost:3000` if `CORS_ORIGINS` is not set
- Allows localhost origins (`http://localhost:*`, `http://127.0.0.1:*`)
- Allows HTTP (non-HTTPS) origins
- More permissive CORS methods and headers

**Example Configuration:**
```env
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Production Environment

**Strict Requirements:**
- **MUST** be explicitly set (no defaults)
- **MUST NOT** contain wildcards (`*`)
- **MUST NOT** contain localhost or 127.0.0.1
- **MUST** use HTTPS for all origins (HTTP is rejected)
- **MUST** specify exact trusted domains

**Example Configuration:**
```env
ENVIRONMENT=production
CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

## Validation

### Application Startup Validation

The application validates CORS configuration at startup via `validate_security_settings()` in `app/config/security.py`. In production, the application will **fail to start** if:

1. CORS_ORIGINS contains `*` (wildcard)
2. CORS_ORIGINS contains `localhost` or `127.0.0.1`
3. CORS_ORIGINS contains HTTP (non-HTTPS) origins
4. CORS_ORIGINS is empty

**Error Example:**
```
CRITICAL: Security validation failed. The application cannot start with insecure settings.

Issues found:
  ❌ CORS_ORIGINS contains '*' - NEVER use wildcards in production
  ❌ CORS_ORIGINS contains localhost/127.0.0.1 - NOT allowed in production
```

### Deployment Script Validation

The `deployment/deploy_app.sh` script also validates CORS configuration before deployment:

- Checks for wildcards
- Checks for localhost/127.0.0.1
- Checks for HTTP (non-HTTPS) origins
- Exits with error if validation fails

## Implementation Details

### Code Locations

1. **Configuration:** `app/config/security.py`
   - `SecuritySettings.cors_origins` field (line 331)
   - `get_cors_origins()` function (line 789)
   - `validate_security_settings()` function (line 684-701)

2. **Middleware:** `app/main.py`
   - CORS middleware configuration (line 83-89)

3. **Deployment:** `deployment/deploy_app.sh`
   - Production validation (line 96-123)

### CORS Methods (Environment-Aware)

**Development:**
- `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `HEAD`

**Production:**
- `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS` (HEAD excluded for security)

### CORS Headers (Environment-Aware)

**Development:**
- `Content-Type`, `Authorization`, `Accept`, `Accept-Language`, `Content-Language`, `X-Requested-With`, `X-API-Key`, `X-CSRF-Token`

**Production:**
- `Content-Type`, `Authorization`, `Accept`, `X-Requested-With`, `X-API-Key` (restricted set)

## Security Best Practices

1. **Never use wildcards** - Always specify exact domains
2. **Never include localhost in production** - Use production domains only
3. **Always use HTTPS in production** - HTTP is automatically rejected
4. **Use comma-separated list** - Multiple origins: `https://app.example.com,https://admin.example.com`
5. **Test in development first** - Verify CORS works before deploying to production

## Troubleshooting

### Application Won't Start in Production

**Error:** "CORS_ORIGINS contains localhost/127.0.0.1 - NOT allowed in production"

**Solution:**
1. Set `CORS_ORIGINS` to your production domain(s)
2. Ensure all origins use HTTPS
3. Remove any localhost or wildcard entries

**Example Fix:**
```env
# Before (will fail)
CORS_ORIGINS=http://localhost:3000

# After (correct)
CORS_ORIGINS=https://app.yourdomain.com
```

### CORS Errors in Browser

**Error:** "Access to fetch at '...' from origin '...' has been blocked by CORS policy"

**Solution:**
1. Verify the origin is in `CORS_ORIGINS`
2. Check that the origin matches exactly (including protocol, domain, and port)
3. Ensure the origin uses HTTPS in production

## Related Documentation

- `SECURITY.md` - General security documentation
- `app/config/security.py` - Security configuration code
- `deployment/deploy_app.sh` - Deployment validation

---

**Note:** This documentation is automatically enforced by the application. The application will refuse to start with insecure CORS settings in production.

