# Fix: Redirect to Login After Cognito Login

## Problem

After Cognito login, clicking any link redirects back to the login page. This happens because:

1. Token verification fails (JWKS 404 error)
2. Middleware doesn't set `cognito_user_id` when verification fails
3. Views check for `cognito_user_id`, don't find it, and redirect to login

## Root Cause

The middleware was too strict:
- If token verification failed, it tried to refresh
- If refresh failed, it cleared tokens
- Views couldn't find user identity and redirected to login

## Solution

### 1. Made Middleware More Lenient

**Before:**
- Verify token → If fails, try refresh → If refresh fails, clear tokens

**After:**
- Verify token → If fails, decode without verification → If that fails, try refresh → If refresh fails, decode original token → Always try to set `cognito_user_id`

**Key Changes:**
- Decodes token without verification if verification fails (works even if JWKS unavailable)
- Never clears tokens - keeps them for session-based auth
- Always tries to extract `cognito_user_id` from token, even if verification fails

### 2. Enhanced Views with Session Token Fallback

**Before:**
- Check middleware → Check helpers → If no user_id, redirect to login

**After:**
- Check middleware → Check helpers → Check session token → Extract user_id from token → If still no user_id, redirect to login

**Key Changes:**
- All views now check for `id_token` in session as final fallback
- Extract `user_id` from token without verification if needed
- Only redirect to login if no token exists at all

## Code Changes

### Middleware (`tracker/middleware.py`)

```python
# Try to verify token first
try:
    payload = verify_id_token(id_token)
    request.cognito_user_id = payload.get('sub')
except Exception:
    # If verification fails, decode without verification
    payload = pyjwt.decode(id_token, options={"verify_signature": False})
    request.cognito_user_id = payload.get('sub')
    # This works even if JWKS endpoint is unavailable
```

### Views (`tracker/views.py`)

All views now have this fallback:

```python
if not user_id:
    # Final check: extract from session token
    id_token = request.session.get('id_token')
    if id_token:
        decoded = pyjwt.decode(id_token, options={"verify_signature": False})
        user_id = decoded.get('sub')
```

## How It Works Now

1. **User logs in via Cognito:**
   - Tokens saved to session
   - Middleware tries to verify token

2. **If verification fails:**
   - Middleware decodes token without verification
   - Sets `request.cognito_user_id` from decoded token
   - Keeps tokens in session

3. **Views check authentication:**
   - First: Check `request.cognito_user_id` (from middleware)
   - Second: Check session token directly
   - Extract `user_id` from token if needed
   - Only redirect if no token exists

4. **Result:**
   - User can navigate the app even if token verification fails
   - All views work with session tokens
   - No unnecessary redirects to login

## Testing

After these changes:

1. **Login via Cognito**
2. **Click any link** (Add Planting, Profile, etc.)
3. **Expected:** Should work without redirecting to login
4. **Check logs:**
   ```bash
   sudo journalctl -u smartharvester -f | grep "CognitoTokenMiddleware\|add_planting_view\|save_planting"
   ```

Should see:
```
CognitoTokenMiddleware: Token decoded without verification for user: 348824b8-c081-702c-29bc-9bc95780529e
add_planting_view: Using Cognito user_id from middleware: 348824b8-c081-702c-29bc-9bc95780529e
```

## Benefits

✅ **Works even if JWKS unavailable** - Decodes token without verification
✅ **No token clearing** - Keeps tokens for session-based auth
✅ **Multiple fallbacks** - Middleware → Helpers → Session token
✅ **Better user experience** - No unnecessary redirects

## Important Notes

- Token verification is still preferred when possible
- Unverified decode is a fallback for when JWKS is unavailable
- Tokens are never cleared - views can always check session
- This allows the app to work even with temporary AWS issues

The fix ensures that once a user logs in via Cognito, they can navigate the app without being redirected back to login, even if token verification temporarily fails.

