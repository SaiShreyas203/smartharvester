# User-Planting Association in DynamoDB

## Overview

When a user adds a planting, it must be permanently associated with that user in the DynamoDB `plantings` table. This ensures:
- ✅ Plantings persist across sessions
- ✅ Each user only sees their own plantings
- ✅ Data is stored permanently in DynamoDB (not just session)

## How It Works

### 1. User Login & Persistence

When a user logs in via Cognito:

1. **`cognito_callback`** receives the authorization code
2. **Exchanges code for tokens** (id_token, access_token, refresh_token)
3. **Calls `persist_cognito_user`** which:
   - Extracts `user_id` (Cognito `sub`) and `username` from the token
   - Saves user to `users` table in DynamoDB
   - Migrates any existing session plantings to the user

### 2. Username Extraction Logic

The username is extracted using this priority (same logic in both `persist_cognito_user` and `save_planting`):

```python
username = (
    claims.get('cognito:username') or      # Primary Cognito username
    claims.get('preferred_username') or    # Preferred username
    claims.get('username') or               # Generic username
    claims.get('email')                     # Email as fallback
)
```

This ensures consistency - the same username used to save the user is used to associate plantings.

### 3. Adding a Planting

When a user adds a planting via `save_planting`:

1. **Extract User Identity:**
   - Check `request.cognito_user_id` (from middleware) - fastest
   - Check session `id_token` - fallback
   - Extract `user_id` (Cognito `sub`) and `username` using same logic as login

2. **Validate User Identity:**
   - Must have `user_id` (required)
   - Must have `username` (required, falls back to `user_id` if missing)

3. **Create Planting Object:**
   ```python
   new_planting = {
       'planting_id': str(uuid.uuid4()),
       'crop_name': crop_name,
       'planting_date': planting_date.isoformat(),
       'batch_id': batch_id,
       'notes': notes,
       'plan': calculated_plan,
       'image_url': image_url,
       'user_id': user_id,      # Cognito sub (e.g., "348824b8-c081-702c-29bc-9bc95780529e")
       'username': username,    # Username from token (e.g., "qwert" or email)
   }
   ```

4. **Save to DynamoDB:**
   - Calls `save_planting_to_dynamodb(new_planting)`
   - Planting is stored with both `user_id` and `username` for flexible querying
   - Returns `planting_id` on success

5. **Save to Session:**
   - Also saves to session for immediate UI display
   - Session is a cache; DynamoDB is the source of truth

### 4. Loading User Plantings

When loading plantings (in `index` view):

1. **Get user_id** from middleware or session
2. **Call `load_user_plantings(user_id)`**
3. **DynamoDB queries:**
   - First tries GSI `user_id-index` (fastest)
   - Falls back to Scan with `user_id` filter
   - Falls back to Scan with `username` filter

## DynamoDB Table Structure

### `plantings` Table

**Partition Key:** `planting_id` (UUID string)

**Attributes:**
- `planting_id` (PK) - Unique identifier
- `user_id` - Cognito sub or `django_<pk>`
- `username` - Username from Cognito or Django
- `crop_name` - Name of the crop
- `planting_date` - ISO date string
- `batch_id` - Batch identifier
- `notes` - User notes
- `plan` - Calculated care plan (list of tasks)
- `image_url` - S3 URL for planting image

**Global Secondary Index (GSI):**
- `user_id-index` - Allows querying by `user_id`

### `users` Table

**Partition Key:** `username` (from Cognito or Django)

**Attributes:**
- `username` (PK) - Username
- `user_id` - Cognito sub or `django_<pk>`
- `email` - User email
- `name` - Full name
- `sub` - Cognito sub (explicit)

## Data Flow Diagram

```
User Login
    ↓
Cognito Callback
    ↓
persist_cognito_user()
    ├─ Extract user_id (sub) and username
    ├─ Save to users table
    └─ Migrate session plantings
        ↓
User Adds Planting
    ↓
save_planting()
    ├─ Extract user_id and username (same logic)
    ├─ Create planting object with user_id + username
    ├─ Save to plantings table (DynamoDB)
    └─ Save to session (cache)
        ↓
User Views Dashboard
    ↓
index()
    ├─ Get user_id from middleware/session
    ├─ load_user_plantings(user_id)
    └─ Query DynamoDB by user_id
```

## Key Requirements

### ✅ Both `user_id` and `username` Required

The planting **must** have both:
- `user_id`: For querying by Cognito sub (stable identifier)
- `username`: For querying by username (matches users table PK)

### ✅ Consistent Username Extraction

The same username extraction logic is used in:
- `persist_cognito_user` (during login)
- `save_planting` (when adding planting)

This ensures the username in plantings matches the username in users table.

### ✅ Error Handling

If DynamoDB save fails:
- Error is logged with clear message
- Planting is still saved to session (for immediate UI)
- User sees warning that data may be lost if session expires

## Verification

### Check Planting Association

After adding a planting, check logs:

```bash
sudo journalctl -u smartharvester -f | grep "save_planting"
```

Should see:
```
save_planting: Using Cognito user_id from middleware: 348824b8-c081-702c-29bc-9bc95780529e, username: qwert
save_planting: Saving planting with user_id=348824b8-c081-702c-29bc-9bc95780529e, username=qwert
✅ Saved planting abc-123-def-456 to DynamoDB for user_id=348824b8-c081-702c-29bc-9bc95780529e, username=qwert
```

### Check DynamoDB

Query the plantings table:

```python
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('plantings')

# Query by user_id
response = table.query(
    IndexName='user_id-index',
    KeyConditionExpression=Key('user_id').eq('348824b8-c081-702c-29bc-9bc95780529e')
)
print(response['Items'])
```

Should show plantings with:
- `user_id`: Your Cognito sub
- `username`: Your username from Cognito

## Troubleshooting

### Issue: Planting not associated with user

**Symptoms:**
- Planting appears in UI but disappears after logout
- Logs show "save_planting_to_dynamodb returned falsy"

**Causes:**
1. Missing `user_id` or `username` in planting object
2. DynamoDB permissions issue (IAM user needs `PutItem` permission)
3. Username doesn't match users table

**Fix:**
1. Check logs for user_id/username extraction
2. Verify DynamoDB permissions (see `docs/FIX_DYNAMODB_PERMISSIONS.md`)
3. Ensure username matches what's in users table

### Issue: Plantings not loading

**Symptoms:**
- User sees no plantings after login
- Logs show "AccessDeniedException" or "No items found"

**Causes:**
1. Wrong `user_id` used in query
2. GSI doesn't exist
3. DynamoDB permissions issue

**Fix:**
1. Check logs: `Index: Using user_id from middleware: ...`
2. Verify GSI exists: `user_id-index` on plantings table
3. Check DynamoDB permissions (Query, Scan)

## Best Practices

1. **Always save both `user_id` and `username`** - Provides flexibility for querying
2. **Use consistent username extraction** - Same logic everywhere
3. **Log user association** - Makes debugging easier
4. **Handle DynamoDB errors gracefully** - Don't crash if save fails
5. **Validate before saving** - Ensure user_id exists before saving planting

## Summary

✅ **User login** → User saved to `users` table with `username` and `user_id`
✅ **Add planting** → Planting saved to `plantings` table with same `user_id` and `username`
✅ **View plantings** → Query `plantings` table by `user_id` to get user's plantings
✅ **Permanent storage** → All plantings stored in DynamoDB, not just session

The association is permanent and persists across sessions, devices, and logins.

