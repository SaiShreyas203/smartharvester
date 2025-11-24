# Notifications Troubleshooting

## Table Created Successfully ✅

The `notifications` table has been created and is ACTIVE in DynamoDB.

## Next Steps

1. **Add a plant** and check your server logs for:
   - `🔔 Attempting to create in-app notification for user_id=...`
   - `✅ Created in-app notification for new planting: notification_id=...`

2. **Open the notifications modal** (click the bell icon) and check:
   - You should see "Planting Added: [crop_name]" notification
   - If you still see "No notifications", check the logs below

## Common Issues

### Issue 1: Still seeing "No notifications" after adding a plant

**Check server logs:**
- Look for: `⚠️ save_notification returned None`
- Look for: `❌ Error creating in-app notification`

**Possible causes:**
1. **user_id mismatch**: The user_id used to save the notification doesn't match the one used to load it
2. **Permissions**: DynamoDB permissions might not allow PutItem/Query/Scan on notifications table
3. **Table not found**: Even though table exists, check if the environment variable `DYNAMO_NOTIFICATIONS_TABLE` is set correctly

**Fix:**
- Check your server logs when adding a plant
- Verify the user_id is the same in both save and load operations
- Check AWS IAM permissions for DynamoDB

### Issue 2: Notifications appear but don't refresh

**Fix:**
- Reload the page or close and reopen the notifications modal
- The modal fetches notifications each time it opens

### Issue 3: Notifications saved but not displayed

**Check:**
- Open browser console (F12) and check for JavaScript errors
- Check the network tab for the `/api/notification-summaries/` request
- Verify the response contains `notifications` array

## Verify Notifications are Working

Run this to check if any notifications exist:

```bash
python -c "import boto3; dynamodb = boto3.resource('dynamodb', region_name='us-east-1'); table = dynamodb.Table('notifications'); resp = table.scan(); print('Total notifications:', len(resp.get('Items', []))); [print(f\"  - {item.get('title', 'No title')} (user: {item.get('user_id', 'unknown')})\") for item in resp.get('Items', [])[:10]]"
```

## Manual Test

1. Add a plant
2. Check server logs - you should see:
   ```
   🔔 Attempting to create in-app notification for user_id=..., crop_name=...
   ✅ Created in-app notification for new planting: notification_id=..., user_id=...
   ```
3. Click the notifications bell icon
4. You should see the notification appear

If you still don't see notifications after these steps, share the server logs and I can help debug further!

