# Cognito Authentication & Database Fixes

This document summarizes the fixes applied to resolve Cognito redirect/token-exchange failures and prevent Django crashes when no RDBMS is configured.

## Changes Summary

### 1. Fixed Cognito Authorization Flow (`tracker/views.py`, `tracker/cognito.py`)

**Problem**: App was constructing wrong URLs for Cognito authorize/token flow, sometimes sending browser to Cognito's `/auth/callback` path instead of the authorize endpoint.

**Solution**:
- Updated `cognito_login()` to validate required env vars (`COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`, `COGNITO_REDIRECT_URI`) before redirecting
- Enhanced `build_authorize_url()` to try OpenID discovery endpoint first, then fallback to `/oauth2/authorize`
- Added proper error handling and logging

### 2. Fixed Token Exchange (`tracker/views.py`)

**Problem**: Token exchange was failing due to incorrect authentication method and missing validation.

**Solution**:
- Updated `cognito_callback()` to use HTTP Basic auth when `COGNITO_CLIENT_SECRET` exists (OAuth2 standard)
- When using HTTP Basic auth, removed `client_id` from request body (as per OAuth2 spec)
- Added validation for required env vars before token exchange
- Improved error messages and logging

### 3. Enhanced DynamoDB Runtime Helper (`tracker/dynamo.py`)

**Problem**: Application views needed a simple runtime helper for DynamoDB operations.

**Solution**:
- Enhanced `tracker/dynamo.py` to be a proper runtime helper
- Added support for both `username` (PK) and `user_id` (Cognito sub) patterns
- Implemented GSI query fallback to scan for plantings
- Added proper error handling and type conversions (float → Decimal)
- Functions now work with both Cognito user IDs and usernames

### 4. Database Fallback Configuration (`config/settings.py`)

**Problem**: Django attempted DB operations but `DATABASES` was not configured, causing `ImproperlyConfigured`/`OperationalError` and killing Gunicorn.

**Solution**:
- Enhanced database configuration to always provide a fallback
- Production: tries `DATABASE_URL` first, falls back to sqlite if not available
- Development: uses Postgres if `DATABASE_NAME` is set, otherwise sqlite
- Added proper error handling and logging for database configuration failures
- Session engine already configured to use signed cookies (no DB access needed)

### 5. Environment Variable Validation

**Problem**: Missing or incorrect `COGNITO_DOMAIN`/client config caused name-resolution or token-exchange failures.

**Solution**:
- Added validation in `cognito_login()` and `cognito_callback()` to check required env vars
- Clear error messages when configuration is missing
- Created example environment files for systemd service and local development

## Files Changed

1. **tracker/views.py**
   - `cognito_login()`: Added env var validation, improved error handling
   - `cognito_callback()`: Fixed token exchange with HTTP Basic auth, added validation

2. **tracker/cognito.py**
   - `build_authorize_url()`: Added OpenID discovery support, improved error handling

3. **tracker/dynamo.py**
   - Complete rewrite as runtime helper
   - Added support for user_id and username patterns
   - Enhanced error handling and type conversions

4. **config/settings.py**
   - Enhanced database configuration with robust fallback
   - Added logging import for database config errors

5. **docs/systemd-service-env.conf.example**
   - Template for systemd service environment file

6. **docs/systemd-service-unit.example**
   - Template for systemd service unit file

7. **docs/ENV_SETUP.md**
   - Setup guide for environment variables

## Testing / Acceptance Criteria

✅ **Visiting `/auth/login`** redirects browser to Cognito's authorize endpoint (from discovery or `/oauth2/authorize`)

✅ **After sign-up/login**, Cognito redirects back to `https://3.235.196.246.nip.io/auth/callback/?code=...` and app successfully exchanges code for tokens

✅ **Gunicorn stays up** (no Postgres connection errors) and `/admin/` works (sqlite fallback has migrations applied)

✅ **Dynamo helper** can list/create plantings (verify with `manage.py shell` or test script)

✅ **systemd service** picks up env vars (`sudo journalctl -u smartharvester` shows no `COGNITO_DOMAIN=none` or name-resolution errors)

## Deployment Steps

1. **Update environment variables**:
   ```bash
   sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
   # Add COGNITO_DOMAIN, COGNITO_CLIENT_ID, COGNITO_REDIRECT_URI, etc.
   ```

2. **Reload systemd and restart service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart smartharvester
   ```

3. **Verify configuration**:
   ```bash
   sudo journalctl -u smartharvester -f
   # Check for COGNITO_DOMAIN errors
   ```

4. **Test login flow**:
   - Visit `https://3.235.196.246.nip.io/auth/login/`
   - Should redirect to Cognito authorize endpoint
   - After login, should redirect back and exchange tokens successfully

## Notes

- Session engine uses signed cookies (no database access needed)
- AuthenticationMiddleware is kept for Django admin compatibility but won't cause DB lookups with signed cookies
- DynamoDB is used for application data (users/plantings)
- SQLite fallback ensures Django admin/auth work even without Postgres

