# Sentry Email Alerts Setup Guide

## Quick Setup Steps

### Step 1: Access Alert Rules

1. **Go to your Sentry project**: https://sentry.io
2. **Navigate to Alerts**:
   - Click on your project (mARB 2.0)
   - In the left sidebar, click **"Alerts"** → **"Alert Rules"**
   - Or go directly to: `https://sentry.io/organizations/[your-org]/alerts/rules/`

### Step 2: Create Your First Alert Rule

1. **Click "Create Alert Rule"** button (top right)

2. **Name Your Alert**:
   - Example: `Critical Errors - Email Alert`
   - Example: `Production Errors - Team Notification`

3. **Set Conditions**:
   - **When**: Choose when to trigger the alert
     - Recommended: "An issue is seen more than **5 times** in **5 minutes**"
     - Or: "An issue is seen more than **10 times** in **10 minutes**"
   - **For issues that match**: (optional filters)
     - **Environment**: Select `production` (or leave blank for all)
     - **Issue level**: Select `error` or `fatal` (exclude warnings/info)
     - **Tags**: (optional) Add filters like `environment:production`

4. **Add Actions**:
   - Click **"Add Action"**
   - Select **"Send a notification via Email"**
   - Enter your **email address** (or multiple addresses separated by commas)
   - Click **"Save Action"**

5. **Save the Alert Rule**:
   - Click **"Save Rule"** at the bottom

### Step 3: Recommended Alert Rules

Here are some useful alert configurations:

#### 1. Critical Errors (High Priority)
```
Name: Critical Errors - Immediate Alert
Condition: An issue is seen more than 5 times in 5 minutes
Filters:
  - Issue level: error or fatal
  - Environment: production
Action: Email to your-email@example.com
```

#### 2. New Error Types (Medium Priority)
```
Name: New Error Types Detected
Condition: A new issue is created
Filters:
  - Environment: production
Action: Email to your-email@example.com
```

#### 3. High Error Rate (Medium Priority)
```
Name: High Error Rate Alert
Condition: The error rate is greater than 5% in 10 minutes
Filters:
  - Environment: production
Action: Email to your-email@example.com
```

#### 4. Performance Degradation (Low Priority)
```
Name: Slow Performance Alert
Condition: P95 latency is greater than 2 seconds in 10 minutes
Filters:
  - Environment: production
Action: Email to your-email@example.com
```

### Step 4: Configure Email Settings

1. **Verify Your Email**:
   - Go to **Settings** → **Account** → **Emails**
   - Make sure your email is verified
   - Add additional email addresses if needed

2. **Email Preferences**:
   - Go to **Settings** → **Notifications**
   - Configure:
     - **Workflow Notifications**: Enable for alerts
     - **Alerts**: Enable email notifications
     - **Frequency**: Choose how often to receive emails

### Step 5: Test Your Alert

1. **Trigger a Test Error**:
   ```bash
   curl http://localhost:8000/sentry-debug
   ```

2. **Wait for Alert**:
   - If the alert condition is met, you should receive an email within a few minutes

3. **Check Email**:
   - Look for an email from Sentry
   - It will include:
     - Error details
     - Stack trace
     - Request context
     - Link to view in Sentry dashboard

## Advanced Configuration

### Alert Frequency Control

To avoid email spam, you can:

1. **Set Higher Thresholds**:
   - Instead of "5 times in 5 minutes", use "20 times in 10 minutes"
   - This reduces noise from transient issues

2. **Use Digest Mode**:
   - In alert actions, you can choose "Send a digest" instead of individual emails
   - This batches multiple alerts into one email

3. **Set Quiet Periods**:
   - Some alert rules allow you to set quiet periods
   - Example: Don't alert if the same issue was already alerted in the last hour

### Team Notifications

1. **Add Team Members**:
   - Go to **Settings** → **Members**
   - Invite team members to your Sentry organization

2. **Team Alerts**:
   - When creating alerts, you can send to:
     - Individual email addresses
     - Team email addresses
     - Slack channels (if integrated)
     - PagerDuty (if integrated)

### Alert Rules Best Practices

1. **Start Conservative**:
   - Begin with higher thresholds (more errors before alerting)
   - Adjust based on your needs

2. **Separate by Environment**:
   - Create different rules for `development`, `staging`, and `production`
   - Production alerts should be more sensitive

3. **Exclude Test Errors**:
   - Add filters to exclude known test endpoints:
     - Tag: `url` does not contain `/sentry-debug`
     - Tag: `environment` equals `production`

4. **Monitor and Adjust**:
   - Review alert frequency after a week
   - Adjust thresholds if you're getting too many or too few alerts

## Troubleshooting

### Not Receiving Emails?

1. **Check Spam Folder**: Sentry emails might be filtered
2. **Verify Email**: Make sure your email is verified in Sentry settings
3. **Check Alert Conditions**: Make sure the alert conditions are actually being met
4. **Check Sentry Logs**: Go to Settings → Integrations → Email to see delivery status

### Too Many Emails?

1. **Increase Thresholds**: Make alerts trigger less frequently
2. **Use Digest Mode**: Batch multiple alerts into one email
3. **Add Filters**: Exclude non-critical errors (warnings, info level)
4. **Set Quiet Periods**: Prevent duplicate alerts for the same issue

### Want More Control?

Consider integrating with:
- **Slack**: Real-time notifications in your team channel
- **PagerDuty**: For on-call rotations and escalation
- **Microsoft Teams**: Similar to Slack integration
- **Webhooks**: Custom integrations with your own systems

## Example Alert Rule Configuration

Here's a complete example for a production critical error alert:

```
Alert Name: Production Critical Errors
Description: Alert when critical errors occur in production

Conditions:
  - When: An issue is seen more than 10 times in 10 minutes
  - For issues that match:
    - Environment: production
    - Issue level: error or fatal
    - Tags: url does not contain "/sentry-debug"

Actions:
  - Send email to: dev-team@yourcompany.com
  - Send email to: oncall@yourcompany.com

Frequency:
  - Quiet period: 1 hour (don't re-alert same issue within 1 hour)
```

## Quick Reference

**Access Alert Rules**: 
- Sentry Dashboard → Your Project → Alerts → Alert Rules

**Create Alert**: 
- Click "Create Alert Rule" → Configure conditions → Add email action → Save

**Test Alert**: 
- Trigger error: `curl http://localhost:8000/sentry-debug`
- Wait 5-10 minutes for email

**Manage Alerts**: 
- Settings → Notifications → Configure email preferences

---

**Need Help?** Check Sentry's official documentation: https://docs.sentry.io/product/alerts/

