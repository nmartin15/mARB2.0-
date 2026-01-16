# Sentry Error Tracking Setup

This document describes how to configure and use Sentry error tracking in mARB 2.0.

## Overview

Sentry is integrated into the application to provide:
- **Error Tracking**: Automatic capture of exceptions and errors
- **Context-Rich Errors**: Errors include request context, user info, and custom tags
- **Performance Monitoring**: Transaction tracing and performance profiling
- **Alerting**: Configurable alerts for errors and warnings
- **HIPAA Compliance**: Automatic filtering of sensitive data (PII/PHI)

## Configuration

### Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Sentry Configuration
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production  # or development, staging, etc.
SENTRY_RELEASE=v2.0.0  # Optional: version/release identifier

# Performance Monitoring
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions (0.0 to 1.0)
SENTRY_PROFILES_SAMPLE_RATE=0.1  # 10% of profiles (0.0 to 1.0)

# Alert Configuration
SENTRY_ENABLE_ALERTS=true  # Enable/disable error reporting
SENTRY_ALERT_ON_ERRORS=true  # Send alerts for errors (5xx)
SENTRY_ALERT_ON_WARNINGS=false  # Send alerts for warnings (4xx)

# Feature Flags
SENTRY_ENABLE_TRACING=true  # Enable performance tracing
SENTRY_ENABLE_PROFILING=false  # Enable profiling (can be expensive)
SENTRY_SEND_DEFAULT_PII=false  # Don't send PII by default (HIPAA compliance)
```

### Getting Your Sentry DSN

1. Sign up for a Sentry account at https://sentry.io
2. Create a new project (select Python/FastAPI)
3. Copy the DSN from the project settings
4. Add it to your `.env` file as `SENTRY_DSN`

### Recommended Settings by Environment

#### Development
```bash
SENTRY_DSN=  # Leave empty to disable in development
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.0  # Disable tracing in dev
SENTRY_ENABLE_ALERTS=false  # Don't spam alerts in dev
```

#### Staging
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=staging
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_WARNINGS=false
```

#### Production
```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # Adjust based on traffic
SENTRY_ENABLE_ALERTS=true
SENTRY_ALERT_ON_ERRORS=true
SENTRY_ALERT_ON_WARNINGS=false  # Usually too noisy
SENTRY_ENABLE_PROFILING=false  # Enable only if needed
```

## Features

### Automatic Error Capture

The following errors are automatically captured:

1. **Application Errors** (`AppError` and subclasses):
   - Server errors (5xx) are always sent to Sentry
   - Client errors (4xx) are sent if `SENTRY_ALERT_ON_WARNINGS=true`

2. **Validation Errors**:
   - Sent if `SENTRY_ALERT_ON_WARNINGS=true`

3. **Unexpected Exceptions**:
   - Always sent to Sentry (unhandled exceptions)

4. **Celery Task Errors**:
   - All task failures are captured with task context

### Context and Tags

Errors automatically include:

- **Request Context**: Path, method, query parameters
- **Error Details**: Error code, message, status code
- **Task Context** (for Celery): Task ID, retries, task name
- **Tags**: Error type, status code, path, task name

### Breadcrumbs

Breadcrumbs are automatically added to provide context about what happened before an error:
- API requests
- Database operations
- Celery task execution
- Validation failures

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
    context={
        "event": {
            "type": "rate_limit_approaching",
            "current_rate": 95,
        },
    },
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

# Set user context for all subsequent errors
set_user_context(
    user_id="123",
    username="john.doe",
    practice_id="practice-456",
)

# Clear user context
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

1. **Critical Errors**:
   - Trigger: More than 10 errors in 5 minutes
   - Action: PagerDuty/Slack notification

2. **High Error Rate**:
   - Trigger: Error rate > 5% in 10 minutes
   - Action: Email notification

3. **New Error Types**:
   - Trigger: New issue created
   - Action: Slack notification

4. **Performance Degradation**:
   - Trigger: P95 latency > 2 seconds
   - Action: Email notification

## Performance Monitoring

### Transaction Tracing

Transaction tracing is enabled by default (10% sample rate). This provides:
- Request duration
- Database query performance
- External API call timing
- Celery task execution time

### Profiling

Profiling is disabled by default (can be expensive). To enable:

```bash
SENTRY_ENABLE_PROFILING=true
SENTRY_PROFILES_SAMPLE_RATE=0.05  # 5% of transactions
```

## Troubleshooting

### Sentry Not Capturing Errors

1. **Check DSN**: Ensure `SENTRY_DSN` is set correctly
2. **Check Environment**: Verify `SENTRY_ENVIRONMENT` matches your environment
3. **Check Alerts**: Ensure `SENTRY_ENABLE_ALERTS=true`
4. **Check Logs**: Look for "Sentry initialized" in application logs

### Too Many Alerts

1. Set `SENTRY_ALERT_ON_WARNINGS=false` to disable warning alerts
2. Adjust alert rules in Sentry dashboard
3. Increase alert thresholds (e.g., "more than 50 errors in 10 minutes")

### Missing Context

1. Ensure you're using `capture_exception()` with context parameter
2. Check that breadcrumbs are being added before errors
3. Verify user context is set when available

### HIPAA Compliance Concerns

1. Verify `SENTRY_SEND_DEFAULT_PII=false`
2. Review Sentry dashboard to ensure no PII/PHI is visible
3. Test with sample errors to verify filtering works
4. Consider using Sentry's on-premise option for maximum control

## Integration Points

### FastAPI Application

Sentry is initialized in `app/main.py` before other imports to ensure all errors are captured.

### Celery Workers

Sentry is initialized in `app/config/celery.py` so Celery workers also capture errors.

### Error Handlers

Error handlers in `app/utils/errors.py` automatically send errors to Sentry with context.

### Celery Tasks

Task error handlers in `app/services/queue/tasks.py` capture task failures with task context.

## Best Practices

1. **Don't Over-Alert**: Only alert on actionable errors
2. **Use Context**: Always provide context when capturing errors
3. **Use Tags**: Tag errors for easy filtering and grouping
4. **Review Regularly**: Review Sentry dashboard weekly to identify patterns
5. **Test Alerts**: Test alert configuration to ensure it works as expected
6. **Monitor Performance**: Use transaction tracing to identify slow endpoints
7. **Respect Privacy**: Never send PII/PHI to Sentry (filtering is automatic, but be careful)

## Resources

- [Sentry Python Documentation](https://docs.sentry.io/platforms/python/)
- [Sentry FastAPI Integration](https://docs.sentry.io/platforms/python/guides/fastapi/)
- [Sentry Celery Integration](https://docs.sentry.io/platforms/python/guides/celery/)
- [Sentry HIPAA Compliance](https://sentry.io/security/)

