# Quick Fix: COGNITO_DOMAIN Not Configured

## Problem

You're seeing this error:
```
Cognito domain not configured. Please set COGNITO_DOMAIN environment variable.
Format: <prefix>.auth.<region>.amazoncognito.com
```

## Quick Fix

### For Local Development (Windows)

Your `.env` file needs to have the correct Cognito domain:

1. **Update `.env` file** in the project root:
   ```
   COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
   ```

2. **Verify** your `.env` file has these Cognito settings:
   ```bash
   COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
   COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
   COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
   COGNITO_REGION=us-east-1
   ```

3. **Restart your Django development server**:
   ```bash
   # Stop the server (Ctrl+C)
   # Start it again
   python manage.py runserver
   ```

### For Production (systemd service on Linux)

1. **Edit the environment file**:
   ```bash
   sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
   ```

2. **Set COGNITO_DOMAIN**:
   ```ini
   COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
   ```

3. **Reload and restart**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart smartharvester
   ```

## Important Notes

- ✅ **Correct format**: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
- ❌ **Wrong format**: `https://smartcrop-rocky-app.auth.us-east-1.amazoncognito.com` (no https://)
- ❌ **Wrong format**: `myuserpool-ui.auth.us-east-1.amazoncognito.com` (old/incorrect domain)

## Your Cognito Details

- **Domain**: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
- **Region**: `us-east-1`
- **Client ID**: `4l8j19f73h5hqmlldgc6jigk3k`
- **Redirect URI**: `https://3.235.196.246.nip.io/auth/callback/`

## Verify It Works

After updating, test by visiting:
```
https://3.235.196.246.nip.io/auth/login/
```

You should be redirected to the Cognito login page (not an error page).

