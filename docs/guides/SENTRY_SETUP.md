# Sentry Error Tracking Setup

This guide covers everything you need to set up and configure Sentry error tracking in mARB 2.0.

## Quick Start (5 minutes)

### Step 1: Create Sentry Account & Project

1. **Sign up/Log in** at https://sentry.io (free tier available)
2. **Create a new project**:
   - Click "Projects" → "Create Project"
   - Select **"Python"** → **"FastAPI"**
   - Enter project name: `mARB 2.0`
   - Click "Create Project"
3. **Copy your DSN** (looks like: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`)

### Step 2: Configure Environment

Add to your `.env` file:

```bash
# Sentry Configuration
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=development  # or staging, production
SENTRY_RELEASE=v2.0.0  # Optional: version identifier

# Performance Monitoring
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions (0.0 to 1.0)
SENTRY_PROFILES_SAMPLE_RATE=0.1  # 10% of profiles (0.0 to 1.0)

# Alert Configuration
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false

# Feature Flags
SENTRY_ENABLE_TRACING=true
SENTRY_ENABLE_PROFILING=false
SENTRY_SEND_DEFAULT_PII=false  # HIPAA compliance
```

### Step 3: Test Configuration

```bash
source venv/bin/activate
python scripts/test_sentry.py
```

### Step 4: Restart Application

Restart your FastAPI server and Celery worker to load the new configuration.

## Overview

Sentry provides:
- **Error Tracking**: Automatic capture of exceptions and errors
- **Context-Rich Errors**: Errors include request context, user info, and custom tags
- **Performance Monitoring**: Transaction tracing and performance profiling
- **Alerting**: Configurable alerts for errors and warnings
- **HIPAA Compliance**: Automatic filtering of sensitive data (PII/PHI)

## Environment-Specific Settings

### Development
```bash
SENTRY_DSN=  # Leave empty to disable in development
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.0
SENTRY_ENABLE_ALERTS=false
```

### Staging
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=staging
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_WARNINGS=false
```

### Production
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false
SENTRY_ENABLE_PROFILING=false
```

## Features

### Automatic Error Capture

The following errors are automatically captured:
- **Application Errors** (`AppError` and subclasses)
- **Validation Errors** (if `SENTRY_ALERT_ON_WARNINGS=true`)
- **Unexpected Exceptions** (always sent)
- **Celery Task Errors** (all task failures)

### Context and Tags

Errors automatically include:
- **Request Context**: Path, method, query parameters
- **Error Details**: Error code, message, status code
- **Task Context** (for Celery): Task ID, retries, task name
- **Tags**: Error type, status code, path, task name

### HIPAA Compliance

Sentry is configured to filter sensitive data:
- Authorization headers are removed
- Cookies are removed
- API keys and tokens are removed
- PII/PHI is filtered from context
- User data is limited to safe identifiers (ID, username)

## Usage in Code

### Capturing Custom Errors

```python
from app.config.sentry import capture_exception, capture_message, add_breadcrumb

# Capture an exception with context
try:
    # Your code
    pass
except Exception as e:
    capture_exception(
        e,
        level="error",
        context={
            "custom_context": {
                "claim_id": claim_id,
                "payer_id": payer_id,
            },
        },
        tags={
            "operation": "claim_processing",
            "payer": payer_name,
        },
    )
    raise

# Capture a message
capture_message(
    "Important event occurred",
    level="warning",
    context={"event": {"type": "rate_limit_approaching"}},
)

# Add a breadcrumb
add_breadcrumb(
    message="Processing claim",
    category="business_logic",
    level="info",
    data={"claim_id": claim_id},
)
```

### Setting User Context

```python
from app.config.sentry import set_user_context, clear_user_context

set_user_context(
    user_id="123",
    username="john.doe",
    practice_id="practice-456",
)

clear_user_context()
```

## Alert Configuration

### Setting Up Alerts in Sentry

1. Go to your Sentry project settings
2. Navigate to **Alerts** → **Create Alert Rule**
3. Configure alert conditions:
   - **Trigger**: When an issue is seen more than X times in Y minutes
   - **Actions**: Email, Slack, PagerDuty, etc.

### Recommended Alert Rules

1. **Critical Errors**: More than 10 errors in 5 minutes → PagerDuty/Slack
2. **High Error Rate**: Error rate > 5% in 10 minutes → Email
3. **New Error Types**: New issue created → Slack
4. **Performance Degradation**: P95 latency > 2 seconds → Email

## Performance Monitoring

Transaction tracing is enabled by default (10% sample rate). This provides:
- Request duration
- Database query performance
- External API call timing
- Celery task execution time

## Troubleshooting

### Sentry Not Capturing Errors
1. Check DSN: Ensure `SENTRY_DSN` is set correctly
2. Check Environment: Verify `SENTRY_ENVIRONMENT` matches your environment
3. Check Alerts: Ensure `SENTRY_ENABLE_ALERTS=true`
4. Check Logs: Look for "Sentry initialized" in application logs

### Too Many Alerts
1. Set `SENTRY_ALERT_ON_WARNINGS=false` to disable warning alerts
2. Adjust alert rules in Sentry dashboard
3. Increase alert thresholds

### Missing Context
1. Ensure you're using `capture_exception()` with context parameter
2. Check that breadcrumbs are being added before errors
3. Verify user context is set when available

## Resources

- [Sentry Python Documentation](https://docs.sentry.io/platforms/python/)
- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/guides/fastapi/)
- [Sentry Celery Integration](https://docs.sentry.io/platforms/python/guides/celery/)

