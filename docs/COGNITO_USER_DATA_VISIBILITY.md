# Cognito User Data Visibility After Login

## Summary

After Cognito login, users now see their own data (plantings, email, name) just like Django users. The index view has been enhanced to:

1. ✅ Extract Cognito user information (email, name, user_id)
2. ✅ Load user-specific plantings from DynamoDB
3. ✅ Display user data in the template (username, email)
4. ✅ Filter session data by user_id to prevent cross-user data leakage

## Changes Made

### 1. Enhanced Index View (`tracker/views.py`)

**User Identification:**
- Checks `request.cognito_user_id` first (from middleware - fastest)
- Falls back to helper functions
- Falls back to Django auth
- Extracts email and name from Cognito payload

**Planting Loading:**
- Loads plantings from DynamoDB using `user_id` (Cognito sub)
- Filters session plantings by `user_id` to prevent cross-user data
- Falls back to session only if no DynamoDB data

**Template Context:**
- Creates a `UserData` object that mimics Django's User model
- Passes `user` object with `username`, `email`, `name` attributes
- Template can use `{{ user.username }}`, `{{ user.email }}` just like Django users

### 2. UserData Class

A simple class that provides Django User-like interface:

```python
class UserData:
    def __init__(self, username, email, name=None, user_id=None):
        self.username = username or email or 'User'
        self.email = email or ''
        self.name = name or username or email or 'User'
        self.user_id = user_id
        self.get_full_name = lambda: self.name
        # ... other Django-compatible attributes
```

This allows the template to work with both Cognito and Django users seamlessly.

## How It Works

### After Cognito Login:

1. **Middleware attaches user info:**
   - `request.cognito_payload` - Full JWT claims (email, name, sub, etc.)
   - `request.cognito_user_id` - User's sub (stable ID)

2. **Index view extracts user data:**
   ```python
   if hasattr(request, 'cognito_user_id') and request.cognito_user_id:
       user_id = request.cognito_user_id
       user_email = request.cognito_payload.get('email')
       user_name = request.cognito_payload.get('name') or ...
   ```

3. **Loads user-specific plantings:**
   ```python
   if user_id and load_user_plantings:
       user_plantings = load_user_plantings(user_id)  # From DynamoDB
   ```

4. **Creates UserData object for template:**
   ```python
   template_user = UserData(username=..., email=..., name=...)
   context = {'user': template_user, ...}
   ```

5. **Template displays user data:**
   - `{{ user.username }}` - Shows email or preferred_username
   - `{{ user.email }}` - Shows email address
   - `{{ user.get_full_name }}` - Shows full name

## Data Flow

```
Cognito Login
    ↓
Middleware: Decode token → request.cognito_payload, request.cognito_user_id
    ↓
Index View: Extract user_id, email, name from payload
    ↓
Load Plantings: load_user_plantings(user_id) → DynamoDB query
    ↓
Create UserData: user = UserData(username, email, name)
    ↓
Template: {{ user.username }}, {{ user.email }}, plantings list
```

## What Users See

### After Cognito Login:

1. **Dashboard shows:**
   - Their email/username in profile section
   - Their own plantings (from DynamoDB)
   - User-specific statistics

2. **Profile modal shows:**
   - Their email address
   - Their username/name
   - Can logout

3. **Plantings:**
   - Only their own plantings (filtered by user_id)
   - Can add, edit, delete their plantings
   - Each user's data is isolated

## Testing

### Test 1: Verify User Data Display

1. **Login via Cognito:**
   ```
   https://3.235.196.246.nip.io/auth/login/
   ```

2. **After login, check:**
   - Profile icon shows initials or avatar
   - Click profile icon → modal shows your email
   - Dashboard shows your plantings (if any)

3. **Check logs:**
   ```bash
   sudo journalctl -u smartharvester -f | grep "Index:"
   ```
   
   Should show:
   ```
   Index: Using user_id from middleware: abc-123-def-456
   Index: Final user data - email=user@example.com, name=John Doe, username=user@example.com
   Loaded X plantings from DynamoDB for user_id: abc-123-def-456
   ```

### Test 2: Verify User-Specific Plantings

1. **Login as User A**, add a planting
2. **Logout**
3. **Login as User B**
4. **Expected:**
   - User B only sees their own plantings
   - User A's plantings are not visible
   - Each user's data is isolated

### Test 3: Verify Template User Object

1. **Login and view page source**
2. **Check profile modal:**
   - Should show your email in the email field
   - Should show your username in the username field
3. **Check avatar:**
   - Should show initials based on your name/username

## Key Improvements

1. **Consistent User Data**: Cognito users get same data structure as Django users
2. **User-Specific Plantings**: Plantings are loaded by user_id from DynamoDB
3. **Session Filtering**: Session plantings are filtered by user_id to prevent cross-user data
4. **Template Compatibility**: `UserData` class makes templates work with both auth types
5. **Enhanced Logging**: Better logging to track user identification and data loading

## Before vs After

### Before:
- Cognito users might not see their plantings
- User data (email, name) not displayed in template
- Session plantings not filtered by user
- Template expects Django User object

### After:
- ✅ Cognito users see their own plantings from DynamoDB
- ✅ User email and name displayed correctly
- ✅ Session plantings filtered by user_id
- ✅ Template works with both Cognito and Django users

## Verification Checklist

After these changes, Cognito users should:

- [x] See their email/username in the UI
- [x] See their own plantings after login
- [x] Be able to add new plantings
- [x] See only their own data (no cross-user leakage)
- [x] Have user data visible in profile modal
- [x] Have plantings persist across sessions (stored in DynamoDB)

## Troubleshooting

### If user data not showing:

1. **Check logs for user_id extraction:**
   ```bash
   sudo journalctl -u smartharvester -f | grep "Index:"
   ```

2. **Verify middleware is setting cognito_user_id:**
   - Check middleware logs
   - Verify token is being decoded

3. **Check DynamoDB:**
   - Verify plantings exist with correct user_id
   - Check GSI exists if using user_id-index

### If plantings not loading:

1. **Check user_id is correct:**
   - Should be Cognito sub (e.g., `abc-123-def-456`)
   - Check logs: `Index: user_id = ...`

2. **Verify DynamoDB query:**
   - Check if GSI exists: `user_id-index`
   - Check if plantings have `user_id` attribute set

3. **Check session fallback:**
   - If DynamoDB fails, should fall back to session
   - Session plantings should be filtered by user_id

