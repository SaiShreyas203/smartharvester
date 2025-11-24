# Setup Cognito Environment Variables

Based on your Cognito configuration, here's how to set up the environment variables.

## Your Cognito Details

- **User Pool ID**: `us-east-1_HGEM2vRNI`
- **Region**: `us-east-1`
- **Domain**: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
- **Client ID**: `4l8j19f73h5hqmlldgc6jigk3k`
- **Client Secret**: None (public client)
- **Redirect URI**: `https://3.235.196.246.nip.io/auth/callback/`
- **Sign-out URI**: `https://3.235.196.246.nip.io/auth/logout/` (or `/accounts/logout/`)

## Quick Setup

### Step 1: Create/Update Environment File

```bash
# Create the directory if it doesn't exist
sudo mkdir -p /etc/systemd/system/smartharvester.service.d

# Create/edit the environment file
sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
```

### Step 2: Add These Variables

Copy and paste this into the file (replace `your-django-secret-key-here` with your actual Django secret key):

```ini
# Cognito Configuration
# COGNITO_USER_POOL_ID is optional (token verification can use COGNITO_DOMAIN)
COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
COGNITO_REGION=us-east-1
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
COGNITO_LOGOUT_REDIRECT_URI=https://3.235.196.246.nip.io/auth/logout/
COGNITO_SCOPE=openid email

# AWS Configuration
AWS_REGION=us-east-1

# DynamoDB Configuration
DYNAMODB_USERS_TABLE_NAME=users
DYNAMODB_PLANTINGS_TABLE_NAME=plantings
DYNAMO_USERS_TABLE=users
DYNAMO_PLANTINGS_TABLE=plantings
DYNAMO_USERS_PK=username

# Django Configuration
DJANGO_SECRET_KEY=your-django-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings
IS_PRODUCTION=False
```

**Important Notes:**
- No `COGNITO_CLIENT_SECRET` needed (public client)
- Replace `your-django-secret-key-here` with your actual Django secret key
- Add AWS credentials if needed for DynamoDB/S3 access

### Step 3: Verify Service Unit File

Make sure your service unit file includes the EnvironmentFile directive:

```bash
# Check the service unit
sudo cat /etc/systemd/system/smartharvester.service | grep EnvironmentFile
```

Should show:
```
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

If missing, add it:
```bash
sudo nano /etc/systemd/system/smartharvester.service
```

Add in `[Service]` section:
```ini
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

### Step 4: Reload and Restart

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart smartharvester

# Check status
sudo systemctl status smartharvester
```

### Step 5: Verify Variables Are Loaded

```bash
# Check if variables are loaded
sudo systemctl show smartharvester --property=Environment | grep COGNITO_DOMAIN

# Should show:
# Environment=COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com ...
```

### Step 6: Test

```bash
# Check logs
sudo journalctl -u smartharvester -f

# Visit in browser:
# https://3.235.196.246.nip.io/auth/login/
```

You should be redirected to Cognito login page.

## Verify Cognito App Client Settings

Make sure in AWS Console → Cognito → User Pools → Your Pool → App integration → App client settings:

✅ **Allowed callback URLs**: 
```
https://3.235.196.246.nip.io/auth/callback/
```

✅ **Allowed sign-out URLs**:
```
https://3.235.196.246.nip.io/logout/
```

✅ **Allowed OAuth flows**: 
- Authorization code grant
- Implicit grant (if needed)

✅ **Allowed OAuth scopes**:
- openid
- email
- profile (if needed)

## Troubleshooting

### If you still see "COGNITO_DOMAIN is not configured":

1. **Verify file exists and has correct content:**
   ```bash
   sudo cat /etc/systemd/system/smartharvester.service.d/env.conf
   ```

2. **Check file permissions:**
   ```bash
   sudo chmod 644 /etc/systemd/system/smartharvester.service.d/env.conf
   ```

3. **Verify EnvironmentFile is in service unit:**
   ```bash
   sudo systemctl show smartharvester | grep EnvironmentFile
   ```

4. **Check if variables are actually loaded:**
   ```bash
   sudo systemctl show smartharvester --property=Environment
   ```

5. **Restart service again:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart smartharvester
   ```

### Test Domain Resolution

```bash
# Test if domain resolves
nslookup smartcrop-rocky-app.auth.us-east-1.amazoncognito.com

# Test discovery endpoint
curl -I https://smartcrop-rocky-app.auth.us-east-1.amazoncognito.com/.well-known/openid-configuration
```

Should return `200 OK` if domain is correct.

## Quick Reference

Your environment file should look like this (minimal required vars):

```ini
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
COGNITO_REGION=us-east-1
```

All other variables are optional or have defaults.

