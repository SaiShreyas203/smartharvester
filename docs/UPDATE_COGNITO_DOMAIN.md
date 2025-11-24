# Update Cognito Domain Environment Variable

## Your Correct Domain

From AWS Console:
- **Domain**: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
- **Full URL**: `https://smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`

## Quick Fix

### Step 1: Update Environment File

```bash
# Edit the environment file
sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
```

**Find this line:**
```ini
COGNITO_DOMAIN=myuserpool-ui.auth.us-east-1.amazoncognito.com
```

**Change it to:**
```ini
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
```

**Important**: 
- ✅ Use the domain WITHOUT `https://` prefix
- ✅ Use the domain WITHOUT trailing slash
- ✅ Format: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`

### Step 2: Verify the File

After editing, verify the change:

```bash
# Check the file contents
sudo cat /etc/systemd/system/smartharvester.service.d/env.conf | grep COGNITO_DOMAIN
```

Should show:
```
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
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
# Check if the new domain is loaded
sudo systemctl show smartharvester --property=Environment | grep COGNITO_DOMAIN
```

Should show:
```
Environment=COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com ...
```

### Step 5: Test

```bash
# Check logs for errors
sudo journalctl -u smartharvester -f

# Test the login URL
# Visit: https://3.235.196.246.nip.io/auth/login/
```

## Complete Environment File Example

Your `/etc/systemd/system/smartharvester.service.d/env.conf` should contain:

```ini
# Cognito Configuration
COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
COGNITO_REGION=us-east-1
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
COGNITO_LOGOUT_REDIRECT_URI=https://3.235.196.246.nip.io/logout/
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

## Common Mistakes

❌ **Wrong**: `COGNITO_DOMAIN=https://smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`  
✅ **Correct**: `COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`

❌ **Wrong**: `COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com/`  
✅ **Correct**: `COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`

❌ **Wrong**: `COGNITO_DOMAIN = smartcrop-rocky-app.auth.us-east-1.amazoncognito.com` (spaces)  
✅ **Correct**: `COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com` (no spaces)

## Verify Domain Works

After updating, test the domain:

```bash
# Test DNS resolution
nslookup smartcrop-rocky-app.auth.us-east-1.amazoncognito.com

# Test discovery endpoint
curl -I https://smartcrop-rocky-app.auth.us-east-1.amazoncognito.com/.well-known/openid-configuration
```

Should return `200 OK` if domain is correct.

## Still Seeing the Old Domain Error?

1. **Double-check the file** - make sure you saved it:
   ```bash
   sudo cat /etc/systemd/system/smartharvester.service.d/env.conf | grep COGNITO_DOMAIN
   ```

2. **Verify service unit includes EnvironmentFile**:
   ```bash
   sudo systemctl show smartharvester | grep EnvironmentFile
   ```

3. **Force reload**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart smartharvester
   ```

4. **Check if variables are actually loaded**:
   ```bash
   sudo systemctl show smartharvester --property=Environment
   ```

5. **Check logs** for the actual domain being used:
   ```bash
   sudo journalctl -u smartharvester -n 50 | grep COGNITO_DOMAIN
   ```

