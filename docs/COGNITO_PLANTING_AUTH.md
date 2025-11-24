# Cognito User Planting Authentication

## Summary

All planting-related views now use the same authentication logic as the index view, ensuring Cognito users can add, edit, update, and delete plantings just like Django users.

## Changes Made

### 1. Enhanced `add_planting_view`
- ✅ Checks for Cognito user first (from middleware)
- ✅ Falls back to helper functions
- ✅ Falls back to Django auth
- ✅ Requires authentication (redirects to login if not authenticated)

### 2. Enhanced `save_planting`
- ✅ Checks for Cognito user first (from middleware) - **same priority as Django users**
- ✅ Uses `request.cognito_user_id` and `request.cognito_payload` from middleware
- ✅ Falls back to helper functions
- ✅ Falls back to Django auth
- ✅ Requires authentication before saving
- ✅ Properly extracts username from Cognito payload

### 3. Enhanced `edit_planting_view`
- ✅ Uses same authentication logic
- ✅ Requires authentication before editing

### 4. Enhanced `update_planting`
- ✅ Uses same authentication logic
- ✅ Requires authentication before updating
- ✅ Uses authenticated user_id for image uploads

### 5. Enhanced `delete_planting`
- ✅ Uses same authentication logic
- ✅ Requires authentication before deleting

## Authentication Flow

All views now follow this consistent pattern:

```python
# 1. Check for Cognito user first (from middleware - fastest)
if hasattr(request, 'cognito_user_id') and request.cognito_user_id:
    user_id = request.cognito_user_id
    # Get username from cognito_payload
    if hasattr(request, 'cognito_payload'):
        username = payload.get('preferred_username') or ...

# 2. Try helper functions
else:
    user_id = get_user_id_from_token(request)
    user_data = get_user_data_from_token(request)

# 3. Fallback to Django auth
if not user_id and request.user.is_authenticated:
    user_id = f"django_{request.user.pk}"
    username = request.user.username

# 4. Require authentication
if not user_id:
    return redirect('login')
```

## How It Works

### After Cognito Login:

1. **Middleware attaches user info:**
   - `request.cognito_payload` - Full JWT claims
   - `request.cognito_user_id` - User's sub (stable ID)

2. **Views check middleware first:**
   - Fastest path - no token decoding needed
   - Direct access to user information

3. **Plantings are saved with user_id:**
   - `user_id`: Cognito sub (e.g., `abc-123-def-456`)
   - `username`: Email or preferred_username from Cognito
   - Both stored in DynamoDB for querying

4. **User-specific data:**
   - Plantings are loaded by `user_id` from DynamoDB
   - Each user only sees their own plantings

## Testing

### Test 1: Add Planting After Cognito Login

1. **Login via Cognito:**
   ```
   https://3.235.196.246.nip.io/auth/login/
   ```

2. **After login, click "Add New Planting"**

3. **Fill in the form and submit**

4. **Expected:**
   - Planting is saved to DynamoDB with your Cognito user_id
   - Planting appears in your dashboard
   - Logs show: `save_planting: Using Cognito user_id from middleware: <your-sub>`

### Test 2: Verify User-Specific Data

1. **Login as User A**, add a planting
2. **Logout**
3. **Login as User B**, add a different planting
4. **Expected:**
   - User A only sees their planting
   - User B only sees their planting
   - No cross-user data leakage

### Test 3: Check Logs

```bash
sudo journalctl -u smartharvester -f | grep -i "save_planting\|add_planting"
```

Should show:
```
save_planting: Using Cognito user_id from middleware: abc-123-def-456
Saved planting abc-123-def-456 to DynamoDB
```

## Key Improvements

1. **Consistent Authentication**: All views use the same logic
2. **Cognito Priority**: Cognito users are checked first (fastest path)
3. **Proper User Identification**: Uses middleware-provided user info
4. **Security**: Requires authentication for all planting operations
5. **Logging**: Enhanced logging to track which user is performing actions

## Before vs After

### Before:
- `save_planting` tried to get user_id but didn't prioritize Cognito middleware
- `add_planting_view` had no authentication check
- Inconsistent user identification across views

### After:
- All views check Cognito middleware first
- All views require authentication
- Consistent user identification pattern
- Cognito users work exactly like Django users

## Verification

After these changes, Cognito users should be able to:
- ✅ Add new plantings
- ✅ Edit existing plantings
- ✅ Update planting details
- ✅ Delete plantings
- ✅ See only their own plantings

All operations will use the Cognito user's `sub` as the `user_id` and their email/username for the `username` field in DynamoDB.

