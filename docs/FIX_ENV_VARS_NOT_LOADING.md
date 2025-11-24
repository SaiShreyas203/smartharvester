# Fix: Environment Variables Not Loading

## The Problem

You're seeing:
```
[ERROR] tracker.views: COGNITO_DOMAIN is not configured
```

This means the environment variables aren't being loaded by your Django application, even though you've set them in the systemd environment file.

## Quick Diagnostic

Run this to check if variables are loaded:
```bash
# Check what Django sees
python manage.py shell -c "from django.conf import settings; print('COGNITO_DOMAIN:', settings.COGNITO_DOMAIN)"

# Or use the diagnostic script
python scripts/check_env_vars.py
```

## Common Causes & Fixes

### 1. Environment File Not Loaded by systemd

**Check if the service unit file includes EnvironmentFile:**

```bash
sudo systemctl show smartharvester | grep EnvironmentFile
```

**Should show:**
```
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

**If missing, add it to your service unit file:**

```bash
# Edit the service unit file
sudo nano /etc/systemd/system/smartharvester.service

# Add this line in the [Service] section:
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

**Then reload:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart smartharvester
```

### 2. Environment File Format Issues

**Check the file exists and has correct format:**

```bash
# Check if file exists
sudo ls -la /etc/systemd/system/smartharvester.service.d/env.conf

# View contents (be careful with secrets)
sudo cat /etc/systemd/system/smartharvester.service.d/env.conf
```

**Correct format (no spaces around =, no quotes needed):**
```ini
COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
```

**Common mistakes:**
- ❌ `COGNITO_DOMAIN = value` (spaces around =)
- ❌ `COGNITO_DOMAIN="value"` (quotes not needed)
- ❌ `export COGNITO_DOMAIN=value` (export not needed in systemd files)
- ✅ `COGNITO_DOMAIN=value` (correct)

### 3. Environment Variables Not Passed to Gunicorn

**Check what environment the service sees:**

```bash
# Check environment variables loaded by systemd
sudo systemctl show smartharvester --property=Environment

# Check environment of running process
sudo cat /proc/$(pgrep -f gunicorn)/environ | tr '\0' '\n' | grep COGNITO
```

**If variables are missing, verify:**

1. **Environment file path is correct** in service unit
2. **File has correct permissions:**
   ```bash
   sudo chmod 644 /etc/systemd/system/smartharvester.service.d/env.conf
   ```

3. **No syntax errors in the file:**
   ```bash
   # Test the file (should show no errors)
   sudo systemd-analyze verify smartharvester.service
   ```

### 4. Django Not Reading Environment

**If systemd has the vars but Django doesn't:**

The issue might be that Django loads settings before environment is available. Check:

1. **Is dotenv loading?** (for .env files in development)
   - Check if `.env` file exists in project root
   - Verify `python-dotenv` is installed

2. **For systemd service**, environment should be loaded automatically via `EnvironmentFile`

3. **Test by adding to service unit directly:**
   ```ini
   [Service]
   Environment="COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com"
   Environment="COGNITO_CLIENT_ID=your-client-id"
   Environment="COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/"
   ```

## Step-by-Step Fix

### Step 1: Verify Environment File

```bash
# Check file exists
sudo test -f /etc/systemd/system/smartharvester.service.d/env.conf && echo "File exists" || echo "File missing"

# View contents
sudo cat /etc/systemd/system/smartharvester.service.d/env.conf
```

**Ensure it contains:**
```ini
COGNITO_DOMAIN=your-actual-domain.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
```

### Step 2: Verify Service Unit Configuration

```bash
# Check service unit file
sudo cat /etc/systemd/system/smartharvester.service

# Look for this line in [Service] section:
# EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

**If missing, add it:**
```bash
sudo nano /etc/systemd/system/smartharvester.service
```

Add in `[Service]` section:
```ini
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

### Step 3: Reload and Restart

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart smartharvester

# Check status
sudo systemctl status smartharvester
```

### Step 4: Verify Variables Are Loaded

```bash
# Method 1: Check systemd environment
sudo systemctl show smartharvester --property=Environment | grep COGNITO_DOMAIN

# Method 2: Check running process
sudo cat /proc/$(pgrep -f gunicorn)/environ | tr '\0' '\n' | grep COGNITO_DOMAIN

# Method 3: Test in Django shell
python manage.py shell -c "from django.conf import settings; print('COGNITO_DOMAIN:', settings.COGNITO_DOMAIN)"
```

**Should show your domain value, not `None`.**

### Step 5: Check Logs

```bash
# Watch logs for errors
sudo journalctl -u smartharvester -f

# Check recent errors
sudo journalctl -u smartharvester -n 50 | grep -i cognito
```

## Alternative: Set Variables Directly in Service Unit

If the environment file approach isn't working, you can set variables directly in the service unit:

```bash
sudo nano /etc/systemd/system/smartharvester.service
```

Add in `[Service]` section:
```ini
[Service]
Environment="COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com"
Environment="COGNITO_CLIENT_ID=your-client-id"
Environment="COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/"
Environment="COGNITO_CLIENT_SECRET=your-secret-if-applicable"
# ... other vars
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart smartharvester
```

## Verification Checklist

- [ ] Environment file exists at `/etc/systemd/system/smartharvester.service.d/env.conf`
- [ ] Environment file has correct format (no spaces, no quotes, no export)
- [ ] Service unit file includes `EnvironmentFile=...` directive
- [ ] File permissions are correct (644)
- [ ] `systemctl daemon-reload` was run after changes
- [ ] Service was restarted after changes
- [ ] Variables show up in `systemctl show smartharvester --property=Environment`
- [ ] Django can see the variables (test with shell command)

## Still Not Working?

1. **Check for typos** in variable names (case-sensitive)
2. **Verify no hidden characters** in the environment file
3. **Check systemd logs**: `sudo journalctl -u smartharvester -n 100`
4. **Try setting variables directly** in service unit (see alternative above)
5. **Restart the entire system** (sometimes systemd needs a full restart)

## Quick Test Command

Run this to see what Django sees:
```bash
python manage.py shell <<EOF
from django.conf import settings
print("COGNITO_DOMAIN:", settings.COGNITO_DOMAIN)
print("COGNITO_CLIENT_ID:", settings.COGNITO_CLIENT_ID)
print("COGNITO_REDIRECT_URI:", settings.COGNITO_REDIRECT_URI)
EOF
```

If these show `None`, the environment variables aren't being loaded.

