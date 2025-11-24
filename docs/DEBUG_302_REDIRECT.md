# Debug: 302 Redirect on POST /save_planting/

## Problem

Getting `"POST /save_planting/ HTTP/1.0" 302 0` - this means the request is being redirected instead of saving the planting.

## What 302 Means

A 302 redirect means the user is not authenticated. The `save_planting` view redirects to login when:
1. No `user_id` can be extracted from the request
2. No token found in session
3. Token extraction fails

## Debugging Steps

### Step 1: Check Authentication Status

Check if you're actually logged in:

```bash
# Check service logs for authentication info
sudo journalctl -u smartharvester -n 100 | grep -i "save_planting\|cognito\|user_id"
```

Look for:
- `save_planting: Using Cognito user_id from middleware`
- `save_planting: No authenticated user found`
- `save_planting: Session keys:`

### Step 2: Check Session Token

The view checks for tokens in this order:
1. `request.cognito_user_id` (from middleware)
2. Helper functions (`get_user_id_from_token`)
3. Session token (`request.session.get('id_token')`)

If all fail, it redirects to login.

### Step 3: Verify Middleware is Working

Check if middleware is setting `cognito_user_id`:

```bash
# Look for middleware logs
sudo journalctl -u smartharvester -n 100 | grep -i "CognitoTokenMiddleware"
```

Should see:
- `CognitoTokenMiddleware: Token verified successfully`
- `CognitoTokenMiddleware: Token decoded without verification`

### Step 4: Check Browser Session

1. Open browser developer tools (F12)
2. Go to Application/Storage → Cookies
3. Check if session cookie exists
4. Check if it has the `id_token` value

## Common Causes

### Cause 1: Session Expired

**Symptoms:**
- Token was valid but expired
- Session cookie missing or invalid

**Fix:**
- Log in again via Cognito
- Check session expiration settings

### Cause 2: Middleware Not Processing Token

**Symptoms:**
- Token exists in session but middleware isn't setting `cognito_user_id`

**Fix:**
- Check middleware logs for errors
- Verify token format is correct
- Check if middleware is enabled in `settings.py`

### Cause 3: Token Extraction Failing

**Symptoms:**
- Token exists but `get_user_id_from_token` returns None

**Fix:**
- Check token format (should be JWT)
- Verify `pyjwt` is installed
- Check logs for token decode errors

### Cause 4: Not Logged In

**Symptoms:**
- No token in session at all
- Never logged in via Cognito

**Fix:**
- Go to `/auth/login/` first
- Complete Cognito login flow
- Then try saving planting

## Enhanced Logging

The code now includes enhanced logging to help diagnose:

1. **Before redirect**: Logs session keys and authentication status
2. **Token extraction**: Logs each step of user_id extraction
3. **On success**: Logs successful save with user_id and username

## Quick Fix

If you're getting 302 redirects:

1. **Make sure you're logged in:**
   ```
   Go to: https://your-domain/auth/login/
   Complete Cognito login
   ```

2. **Check logs after login:**
   ```bash
   sudo journalctl -u smartharvester -f
   ```
   Should see: `Cognito callback: Tokens saved to session`

3. **Try saving planting again:**
   - Fill out the form
   - Submit
   - Check logs for authentication status

## Expected Log Flow (Success)

When saving works correctly, you should see:

```
save_planting: Using Cognito user_id from middleware: 348824b8-c081-702c-29bc-9bc95780529e, username: qwert
save_planting: Saving planting with user_id=348824b8-c081-702c-29bc-9bc95780529e, username=qwert
✅ Saved planting abc-123 to DynamoDB for user_id=348824b8-c081-702c-29bc-9bc95780529e, username=qwert
✅ Saved planting to session: total=1, planting_id=abc-123
save_planting: Successfully saved planting, redirecting to index
```

## Expected Log Flow (Failure - 302)

When authentication fails, you'll see:

```
save_planting: No authenticated user found - no token in session
save_planting: Session keys: ['sessionid']
save_planting: Has cognito_user_id attr: False
"POST /save_planting/ HTTP/1.0" 302 0
```

## Solution

The most common fix is to **log in via Cognito first**:

1. Go to `/auth/login/`
2. Complete Cognito authentication
3. You'll be redirected back with tokens in session
4. Then try saving the planting

The enhanced logging will now show exactly why authentication is failing, making it easier to diagnose the issue.

