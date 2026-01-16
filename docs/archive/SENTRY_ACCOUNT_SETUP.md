# Sentry Account Setup - Step by Step

## 🎯 Overview

**Yes, you absolutely need to set up a Sentry account first!** This guide walks you through the entire process from account creation to getting your DSN.

---

## Step 1: Create Your Sentry Account

### Option A: New Account (Sign Up)

1. **Go to Sentry Signup Page**:
   - Visit: https://sentry.io/signup/
   - Or click the signup link in the browser

2. **Sign Up**:
   - Enter your **email address**
   - Create a **password** (must be at least 8 characters)
   - Click **"Create Account"** or **"Sign Up"**

3. **Verify Your Email** (if required):
   - Check your email inbox
   - Click the verification link
   - Return to Sentry

4. **Complete Onboarding**:
   - You may be asked to select your use case (select "Error Monitoring" or "Application Performance")
   - You may be asked about your team size (select what applies)
   - **Skip any optional steps** if you just want to get started quickly

### Option B: Existing Account (Log In)

1. **Go to Sentry Login Page**:
   - Visit: https://sentry.io/auth/login/

2. **Log In**:
   - Enter your email and password
   - Click **"Log In"**

---

## Step 2: Create a Project

After logging in, you'll see your Sentry dashboard. Now create a project:

1. **Click "Create Project"** button
   - Usually a large button on the dashboard
   - Or go to: **Projects** → **Create Project** (in the sidebar)

2. **Select Platform**:
   - Choose **"Python"** from the list of platforms
   - Then select **"FastAPI"** as the framework

3. **Name Your Project**:
   - Enter a name like: `mARB 2.0` or `mARB Risk Engine`
   - This is just for your reference

4. **Click "Create Project"**

---

## Step 3: Get Your DSN

After creating the project, Sentry will show you a setup page with your **DSN** (Data Source Name).

### What is a DSN?
- It's a unique URL that identifies your Sentry project
- It looks like: `https://xxxxx@xxxxx.ingest.sentry.io/xxxxx`
- You'll add this to your `.env` file

### Where to Find Your DSN:

**Option 1: Setup Page** (Right after creating project)
- The DSN is displayed prominently on the setup page
- **Copy it immediately** - you'll need it!

**Option 2: Project Settings** (If you missed it)
1. Go to your project dashboard
2. Click **Settings** (gear icon) in the sidebar
3. Go to **Projects** → **Your Project Name**
4. Click on **"Client Keys (DSN)"** in the left menu
5. Copy the DSN shown

### DSN Format:
```
https://[key]@[organization].ingest.sentry.io/[project-id]
```

Example:
```
https://abc123def456@o1234567.ingest.sentry.io/1234567890
```

---

## Step 4: Add DSN to Your .env File

1. **Open your `.env` file** in the project root

2. **Add these lines**:
   ```bash
   # Sentry Error Tracking Configuration
   SENTRY_DSN=https://your-actual-dsn-here@sentry.io/project-id
   SENTRY_ENVIRONMENT=development
   ```

3. **Replace** `https://your-actual-dsn-here@sentry.io/project-id` with your actual DSN

4. **Save the file**

---

## Step 5: Test Your Configuration

Run the test script to verify everything works:

```bash
source venv/bin/activate
python scripts/test_sentry.py
```

This will:
- ✅ Check if your DSN is configured
- ✅ Send a test message to Sentry
- ✅ Verify the connection works

---

## Step 6: Verify in Sentry Dashboard

1. **Go back to your Sentry dashboard**: https://sentry.io
2. **Click on your project** (mARB 2.0)
3. **Check "Issues"** tab - you should see:
   - A test message from `test_sentry.py`
   - Any errors that occur in your application

---

## 🎉 Success!

If you see test messages in your Sentry dashboard, you're all set! Sentry will now automatically:
- Capture all exceptions in your application
- Track performance metrics
- Send alerts (if configured)
- Filter sensitive data (HIPAA compliant)

---

## ❓ Troubleshooting

### "I can't find the DSN"
- Go to: **Settings** → **Projects** → **Your Project** → **Client Keys (DSN)**
- The DSN is the long URL starting with `https://`

### "I created the project but lost the DSN"
- No problem! Go to project settings (see above)
- The DSN is always available there

### "The DSN doesn't work"
- Make sure you copied the **entire** DSN (it's long!)
- Check that it starts with `https://`
- Make sure there are no extra spaces
- Restart your application after adding it

### "I want to use a different project"
- You can create multiple projects in Sentry
- Each project has its own DSN
- Just use the DSN from the project you want

---

## 📚 Next Steps

After setting up your account and DSN:

1. ✅ Test with `python scripts/test_sentry.py`
2. ✅ Restart your application
3. ✅ Configure alert rules in Sentry dashboard (optional)
4. ✅ See `SENTRY_SETUP.md` for advanced configuration

---

## 💡 Pro Tips

- **Free Tier**: Sentry's free tier includes 5,000 events/month - perfect for getting started
- **Multiple Environments**: You can use the same project for dev/staging/prod, or create separate projects
- **Team Access**: You can invite team members to your Sentry organization later
- **Alerts**: Set up email/Slack alerts in Sentry dashboard after setup

---

**Ready?** Start with Step 1 above! 🚀

