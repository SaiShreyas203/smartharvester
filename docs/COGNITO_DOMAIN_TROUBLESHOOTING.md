# Cognito Domain Troubleshooting

## Common Error: Name Resolution Failed

If you see an error like:
```
HTTPSConnectionPool(host='myuserpool-ui.auth.us-east-1.amazoncognito.com', port=443): 
Max retries exceeded with url: /oauth2/token 
(Caused by NameResolutionError(": Failed to resolve 'myuserpool-ui.auth.us-east-1.amazoncognito.com'"))
```

This means the Cognito domain cannot be resolved. Here's how to fix it:

## Step 1: Verify Your Cognito Domain

1. **Go to AWS Console** → **Cognito** → **User Pools** → Select your User Pool
2. **Navigate to**: **App integration** tab → **Domain** section
3. **Check the domain name** listed there

The domain should look like one of these formats:
- Default Cognito domain: `<prefix>.auth.<region>.amazoncognito.com`
- Custom domain: `<your-custom-domain>.com`

## Step 2: Check Your Environment Variable

Verify that `COGNITO_DOMAIN` matches exactly what's shown in the AWS Console:

```bash
# Check current value
echo $COGNITO_DOMAIN

# Or for systemd service
sudo systemctl show smartharvester --property=Environment | grep COGNITO_DOMAIN
```

## Step 3: Common Issues

### Issue 1: Domain Doesn't Exist

**Symptom**: Domain shown in error doesn't match what's in AWS Console

**Solution**: 
- Update `COGNITO_DOMAIN` to match the domain in AWS Console exactly
- If no domain exists, create one:
  1. Go to Cognito User Pool → App integration → Domain
  2. Click "Create Cognito domain" or "Create custom domain"
  3. Enter a prefix (for default domain) or configure custom domain
  4. Save the domain name and update your environment variable

### Issue 2: Wrong Domain Format

**Symptom**: Domain format looks incorrect

**Correct formats**:
- ✅ `myapp.auth.us-east-1.amazoncognito.com`
- ✅ `myapp.auth.eu-west-1.amazoncognito.com`
- ✅ `auth.myapp.com` (custom domain)

**Incorrect formats**:
- ❌ `myuserpool-ui` (missing `.auth.region.amazoncognito.com`)
- ❌ `myuserpool-ui.auth` (incomplete)
- ❌ `https://myapp.auth.us-east-1.amazoncognito.com` (includes protocol)

**Solution**: Remove any protocol (`https://`) and ensure full domain format

### Issue 3: Domain Not Created Yet

**Symptom**: You see a placeholder like `myuserpool-ui` in your config

**Solution**: 
1. Go to AWS Console → Cognito → Your User Pool
2. Create a domain (either Cognito domain or custom domain)
3. Copy the exact domain name
4. Update `COGNITO_DOMAIN` environment variable

### Issue 4: Custom Domain DNS Not Configured

**Symptom**: Using custom domain but DNS resolution fails

**Solution**:
1. Verify DNS records are configured correctly in Route 53 or your DNS provider
2. Check that the domain points to the Cognito domain shown in AWS Console
3. Wait for DNS propagation (can take up to 48 hours)

## Step 4: Update Environment Variable

### For systemd Service:

```bash
# Edit the environment file
sudo nano /etc/systemd/system/smartharvester.service.d/env.conf

# Update COGNITO_DOMAIN to the correct value
COGNITO_DOMAIN=your-actual-domain.auth.us-east-1.amazoncognito.com

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart smartharvester
```

### For Local Development:

```bash
# Edit .env file
nano .env

# Update COGNITO_DOMAIN
COGNITO_DOMAIN=your-actual-domain.auth.us-east-1.amazoncognito.com
```

## Step 5: Verify the Fix

1. **Check logs**:
   ```bash
   sudo journalctl -u smartharvester -f
   ```

2. **Test the domain**:
   ```bash
   curl -I https://your-domain.auth.us-east-1.amazoncognito.com/.well-known/openid-configuration
   ```
   Should return `200 OK` if domain is correct

3. **Test login**:
   - Visit `https://your-app-url/auth/login/`
   - Should redirect to Cognito login page (not error)

## Quick Reference: Finding Your Cognito Domain

1. AWS Console → Cognito → User Pools
2. Select your User Pool
3. **App integration** tab
4. **Domain** section
5. Copy the domain name shown (e.g., `myapp-abc123.auth.us-east-1.amazoncognito.com`)

## Example: Correct Configuration

```ini
# In /etc/systemd/system/smartharvester.service.d/env.conf
COGNITO_DOMAIN=myapp-abc123.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=1a2b3c4d5e6f7g8h9i0j
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
COGNITO_CLIENT_SECRET=optional-secret-if-applicable
```

**Note**: Replace `myapp-abc123` with your actual domain prefix from AWS Console.

