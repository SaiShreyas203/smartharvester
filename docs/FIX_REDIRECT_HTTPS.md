# Fix: Redirect to HTTP Instead of HTTPS After Cognito Login

## The Problem

After Cognito login, you're being redirected to:
```
http://3.235.196.246.nip.io:8000/
```

Instead of:
```
https://3.235.196.246.nip.io/
```

## The Fix

I've updated the code to construct the redirect URL from your `COGNITO_REDIRECT_URI` setting, which ensures it uses HTTPS.

## Additional Configuration

### Option 1: If Using a Reverse Proxy (Recommended)

If you're using nginx or another reverse proxy that terminates TLS:

1. **Ensure your reverse proxy forwards the protocol:**
   ```nginx
   # nginx example
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header Host $host;
   ```

2. **Django is already configured** with:
   ```python
   SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
   ```

3. **Your app should run on HTTP internally** (e.g., port 8000), and the proxy handles HTTPS.

### Option 2: If Accessing Directly on Port 8000

If you're accessing the app directly on port 8000:

1. **Set up HTTPS on the application server** (use a reverse proxy like nginx)
2. **Or configure Django to force HTTPS** by setting:
   ```bash
   # In your environment file
   USE_TLS=True
   ```

   This will:
   - Redirect all HTTP requests to HTTPS
   - Set secure cookies
   - Require HTTPS for all connections

### Option 3: Update Cognito Redirect URI

Make sure your Cognito app client settings match your actual access pattern:

- **If using HTTPS**: `https://3.235.196.246.nip.io/auth/callback/`
- **If using HTTP on port 8000**: `http://3.235.196.246.nip.io:8000/auth/callback/`

**Note**: Using HTTP is not recommended for production. Always use HTTPS.

## Verify the Fix

After the code update:

1. **Restart the service:**
   ```bash
   sudo systemctl restart smartharvester
   ```

2. **Test the login flow:**
   - Visit: `https://3.235.196.246.nip.io/auth/login/`
   - Complete Cognito login
   - Should redirect to: `https://3.235.196.246.nip.io/` (not HTTP, not port 8000)

## Recommended Setup

For production, use this setup:

```
Internet → HTTPS (443) → Nginx/Reverse Proxy → HTTP (8000) → Gunicorn/Django
```

This way:
- Users access via HTTPS
- Nginx handles SSL/TLS termination
- Internal communication is HTTP (faster, simpler)
- Django sees requests as HTTPS via `X-Forwarded-Proto` header

## Check Current Configuration

```bash
# Check what URL Django is using
python manage.py shell -c "from django.conf import settings; print('Redirect URI:', settings.COGNITO_REDIRECT_URI)"

# Check if behind proxy
curl -I https://3.235.196.246.nip.io/auth/login/
# Look for X-Forwarded-Proto header in response
```

## Still Redirecting to HTTP?

1. **Check your reverse proxy configuration** (if using one)
2. **Verify `COGNITO_REDIRECT_URI` is set to HTTPS** in your environment file
3. **Check Django logs** for the redirect URL being used:
   ```bash
   sudo journalctl -u smartharvester -f | grep "Redirecting to"
   ```
4. **Ensure `SECURE_PROXY_SSL_HEADER` is set** in settings.py (already configured)

