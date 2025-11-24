# Debug Notifications Not Showing

## Step-by-Step Debugging

### 1. Check Browser Console

Open your browser's Developer Tools (F12) and check the Console tab when you open the notifications modal:

- Look for: `Notification API Response:` - This shows what the API returned
- Look for: `Total notifications:` - Should be > 0 if notifications exist
- Look for any errors in red

### 2. Check Server Logs

When you add a plant, check your server logs for:

```
🔔 Attempting to create in-app notification for user_id=..., crop_name=...
✅ Saved notification ... for user ...: Planting Added: ...
✅ Created in-app notification for new planting: notification_id=...
```

When you open the notifications modal, check for:

```
📥 Loading notifications for user_id=..., limit=50, unread_only=False
✅ Loaded X notifications for user ... via GSI (or via scan)
📊 get_notification_summaries: Returning X notifications for user_id=...
```

### 3. Common Issues

#### Issue A: Notifications saved but not loaded

**Symptom:** You see "✅ Saved notification" but not "✅ Loaded X notifications"

**Cause:** user_id mismatch between save and load

**Fix:** Check that the same user_id is used in both operations. Logs should show the same user_id.

#### Issue B: Table doesn't exist error

**Symptom:** `❌ Notifications table 'notifications' does not exist in DynamoDB!`

**Fix:** Run `python scripts/create_notifications_table.py`

#### Issue C: No notifications in response

**Symptom:** Browser console shows `Total notifications: 0`

**Debug:**
1. Check if user_id is being extracted correctly
2. Check server logs for "📥 Loading notifications"
3. Manually check DynamoDB table for notifications

### 4. Manual Check

Run this to see all notifications in the table:

```bash
python -c "import boto3; dynamodb = boto3.resource('dynamodb', region_name='us-east-1'); table = dynamodb.Table('notifications'); resp = table.scan(); items = resp.get('Items', []); print(f'Total: {len(items)}'); [print(f\"  User: {i.get('user_id')}, Type: {i.get('notification_type')}, Title: {i.get('title')}\") for i in items[:10]]"
```

This will show:
- Total notifications in table
- User IDs
- Notification types
- Titles

### 5. Check User ID Consistency

The user_id used to save notifications must match the one used to load them. Check logs for:

- When saving: `Saved notification ... for user <user_id>`
- When loading: `Loading notifications for user_id=<user_id>`

If they don't match, that's the problem!

### 6. API Endpoint Test

Test the API endpoint directly:

```bash
# Replace with your actual session cookie or auth token
curl -X GET "http://your-server/api/notification-summaries/" \
  -H "Cookie: sessionid=..." \
  | python -m json.tool
```

Look for:
- `"success": true`
- `"notifications": [...]` array with items
- `"count": X` where X > 0

### 7. JavaScript Debug

Add this to browser console after opening notifications modal:

```javascript
fetch('/api/notification-summaries/', {
    headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}
})
.then(r => r.json())
.then(d => console.log('API Response:', d))
```

This will show exactly what the API is returning.

## Still Not Working?

Share:
1. Browser console output (especially "Notification API Response")
2. Server logs when adding a plant
3. Server logs when opening notifications modal
4. Output of the manual check command above

