# DynamoDB Priority Loading (Not Session-Based)

## Overview

After re-login, all plantings (including images and details) are loaded from DynamoDB, not from session. Session is only used as a fallback if DynamoDB query fails.

## Key Changes

### 1. Always Prioritize DynamoDB

**Before:**
- Loaded from DynamoDB if it returned data
- Fell back to session if DynamoDB returned empty list

**After:**
- **Always loads from DynamoDB** when `user_id` exists
- Only uses session if DynamoDB query **fails** (exception)
- If DynamoDB returns empty list, that's correct - user has no plantings

### 2. Type Conversion

DynamoDB stores numbers as `Decimal` types. The code now converts them to Python types:

```python
from decimal import Decimal

def convert_dynamo_types(obj):
    """Convert DynamoDB types to Python types."""
    if isinstance(obj, Decimal):
        # Convert Decimal to float or int
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_dynamo_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_dynamo_types(item) for item in obj]
    return obj
```

### 3. Field Extraction

All fields from DynamoDB are properly extracted, including:
- `image_url` - S3 URL for planting images
- `crop_name` - Name of the crop
- `planting_date` - ISO date string
- `batch_id` - Batch identifier
- `notes` - User notes
- `plan` - Calculated care plan
- `user_id` - User identifier
- `username` - Username

## Loading Flow

```
User Re-Login
    ↓
index() view called
    ↓
Extract user_id from middleware/session
    ↓
Load from DynamoDB (ALWAYS if user_id exists)
    ├─ Query GSI user_id-index (fastest)
    ├─ Fallback: Scan with user_id filter
    └─ Convert DynamoDB types (Decimal → int/float)
        ↓
    Success → Use DynamoDB data (images, details, everything)
    Failure → Fallback to session (only if exception)
        ↓
Display plantings with all details from DynamoDB
```

## Code Logic

```python
# ALWAYS load from DynamoDB first if user_id exists
if user_id and load_user_plantings:
    try:
        dynamodb_plantings = load_user_plantings(user_id)
        if dynamodb_plantings:
            # Convert DynamoDB types
            user_plantings = [convert_dynamo_types(p) for p in dynamodb_plantings]
            logger.info('✅ Loaded %d plantings from DynamoDB (permanent storage)')
        else:
            # Empty list = user has no plantings (correct behavior)
            user_plantings = []
    except Exception:
        # Only use session if DynamoDB query fails
        dynamodb_load_failed = True

# Session fallback ONLY if DynamoDB failed
if dynamodb_load_failed:
    # Use session as temporary fallback
```

## Benefits

### ✅ Permanent Storage
- Plantings persist across sessions, devices, and logins
- Not lost when session expires

### ✅ Complete Data
- All fields loaded: images, notes, plans, dates
- Nothing missing from session-only storage

### ✅ User Isolation
- Each user only sees their own plantings
- Queried by `user_id` from DynamoDB

### ✅ Performance
- Uses GSI `user_id-index` for fast queries
- Falls back to scan only if GSI doesn't exist

## Verification

### Check Logs

After re-login, check logs:

```bash
sudo journalctl -u smartharvester -f | grep "Loaded.*plantings from DynamoDB"
```

Should see:
```
✅ Loaded 3 plantings from DynamoDB for user_id: 348824b8-c081-702c-29bc-9bc95780529e (permanent storage)
```

### Check Image URLs

Verify images are loaded:

```bash
sudo journalctl -u smartharvester -f | grep "image_url"
```

Should see:
```
Planting 0 has image_url: https://s3.amazonaws.com/bucket/planting-123.jpg
```

### Test Re-Login

1. **Login and add a planting with image**
2. **Logout**
3. **Login again**
4. **Expected:**
   - ✅ Planting appears with image
   - ✅ All details (notes, dates, plan) are present
   - ✅ Logs show "Loaded from DynamoDB"

## Troubleshooting

### Issue: Plantings not loading after re-login

**Symptoms:**
- User sees no plantings after re-login
- Logs show "DynamoDB returned empty list"

**Causes:**
1. Plantings not saved to DynamoDB (check `save_planting` logs)
2. Wrong `user_id` used in query
3. DynamoDB permissions issue

**Fix:**
1. Check if plantings were saved: `sudo journalctl -u smartharvester | grep "Saved planting.*to DynamoDB"`
2. Verify `user_id` matches: `sudo journalctl -u smartharvester | grep "user_id"`
3. Check DynamoDB permissions (see `docs/FIX_DYNAMODB_PERMISSIONS.md`)

### Issue: Images not showing

**Symptoms:**
- Plantings load but images are missing
- `image_url` is empty in logs

**Causes:**
1. Image not uploaded to S3
2. `image_url` not saved to DynamoDB
3. S3 permissions issue

**Fix:**
1. Check S3 upload logs: `sudo journalctl -u smartharvester | grep "upload_planting_image"`
2. Verify `image_url` in DynamoDB: Query plantings table
3. Check S3 bucket permissions

### Issue: Using session instead of DynamoDB

**Symptoms:**
- Logs show "⚠️ Using plantings from session (DynamoDB failed)"

**Causes:**
1. DynamoDB query exception (permissions, network, etc.)
2. GSI doesn't exist

**Fix:**
1. Check error logs: `sudo journalctl -u smartharvester | grep "Error loading from DynamoDB"`
2. Verify GSI exists: `user_id-index` on plantings table
3. Check DynamoDB permissions (Query, Scan)

## Summary

✅ **After re-login:** Plantings loaded from DynamoDB (permanent storage)
✅ **All fields:** Images, notes, dates, plans - everything loaded
✅ **Type conversion:** DynamoDB Decimal types converted to Python types
✅ **Session fallback:** Only used if DynamoDB query fails (exception)
✅ **User isolation:** Each user only sees their own plantings

The system now prioritizes DynamoDB as the source of truth, ensuring all data (including images) persists across sessions and logins.

