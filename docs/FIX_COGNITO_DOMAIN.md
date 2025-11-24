# Quick Fix: Cognito Domain Error

## The Problem

You're seeing this error:
```
Cognito domain 'myuserpool-ui.auth.us-east-1.amazoncognito.com' cannot be resolved.
```

This means the domain in your `COGNITO_DOMAIN` environment variable doesn't exist or can't be reached.

## Quick Fix (5 minutes)

### Step 1: Find Your Actual Cognito Domain

**Option A: Using AWS Console (Recommended)**
1. Go to [AWS Console](https://console.aws.amazon.com/)
2. Navigate to **Cognito** → **User Pools**
3. Click on your User Pool
4. Go to **App integration** tab
5. Scroll to **Domain** section
6. **Copy the domain name** shown there (e.g., `myapp-abc123.auth.us-east-1.amazoncognito.com`)

**Option B: Using AWS CLI**
```bash
aws cognito-idp describe-user-pool-domain --domain your-prefix
# Or list all domains:
aws cognito-idp list-user-pool-domains
```

### Step 2: Verify the Domain

Run the verification script:
```bash
# Set the domain temporarily
export COGNITO_DOMAIN=your-actual-domain-from-step-1.auth.us-east-1.amazoncognito.com

# Run verification
python scripts/verify_cognito_domain.py
```

If verification passes, proceed to Step 3.

### Step 3: Update Environment Variable

**For systemd service:**
```bash
# Edit the environment file
sudo nano /etc/systemd/system/smartharvester.service.d/env.conf

# Update this line with your actual domain:
COGNITO_DOMAIN=your-actual-domain.auth.us-east-1.amazoncognito.com

# Save and exit (Ctrl+X, then Y, then Enter)
```

**For local development (.env file):**
```bash
# Edit .env file
nano .env

# Update:
COGNITO_DOMAIN=your-actual-domain.auth.us-east-1.amazoncognito.com
```

### Step 4: Restart Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart smartharvester

# Check logs to verify
sudo journalctl -u smartharvester -f
```

### Step 5: Test

Visit your login URL:
```
https://3.235.196.246.nip.io/auth/login/
```

You should be redirected to Cognito login page (not an error).

## If Domain Doesn't Exist

If you don't see a domain in the AWS Console:

1. **Create a Cognito Domain:**
   - In Cognito User Pool → **App integration** → **Domain**
   - Click **Create Cognito domain**
   - Enter a prefix (e.g., `myapp`)
   - Click **Create domain**
   - Wait a few seconds for it to be created
   - Copy the full domain name (e.g., `myapp-abc123.auth.us-east-1.amazoncognito.com`)

2. **Update your environment variable** with the new domain

3. **Restart the service**

## Common Mistakes

❌ **Wrong**: `COGNITO_DOMAIN=https://myapp.auth.us-east-1.amazoncognito.com`  
✅ **Correct**: `COGNITO_DOMAIN=myapp.auth.us-east-1.amazoncognito.com`

❌ **Wrong**: `COGNITO_DOMAIN=myuserpool-ui` (incomplete)  
✅ **Correct**: `COGNITO_DOMAIN=myapp-abc123.auth.us-east-1.amazoncognito.com` (full domain)

❌ **Wrong**: Using a placeholder like `myuserpool-ui`  
✅ **Correct**: Using the actual domain from AWS Console

## Verification Commands

```bash
# Check current value
echo $COGNITO_DOMAIN

# For systemd service
sudo systemctl show smartharvester --property=Environment | grep COGNITO_DOMAIN

# Test domain resolution
nslookup your-domain.auth.us-east-1.amazoncognito.com

# Test discovery endpoint
curl -I https://your-domain.auth.us-east-1.amazoncognito.com/.well-known/openid-configuration
```

## Still Having Issues?

1. **Double-check the domain** in AWS Console matches exactly what you set
2. **Wait a few minutes** if you just created the domain (DNS propagation)
3. **Check service logs**: `sudo journalctl -u smartharvester -n 50`
4. **Verify environment file is loaded**: `sudo systemctl show smartharvester | grep EnvironmentFile`

For more detailed troubleshooting, see [COGNITO_DOMAIN_TROUBLESHOOTING.md](./COGNITO_DOMAIN_TROUBLESHOOTING.md).

