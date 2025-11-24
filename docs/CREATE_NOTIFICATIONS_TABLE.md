# Create Notifications Table

The in-app notifications feature requires a DynamoDB table called `notifications` to store notification data.

## Quick Fix

Run this script to create the table:

```bash
python scripts/create_notifications_table.py
```

This will create:
- **Table name**: `notifications`
- **Partition key**: `notification_id` (String)
- **GSI (Global Secondary Index)**: `user_id-index` for efficient querying by user
- **Billing mode**: Pay-per-request (on-demand)

## Verify Table Creation

After running the script, you should see:
```
✓ Table 'notifications' created successfully!
✓ GSI 'user_id-index' created successfully!
```

## Test Notifications

1. Add a plant → You should see a "Planting Added" notification
2. Edit a plant → You should see a "Planting Updated" notification
3. Delete a plant → You should see a "Planting Deleted" notification

## Troubleshooting

### If the script fails:

1. **Check AWS credentials**:
   ```bash
   aws sts get-caller-identity
   ```

2. **Check AWS region**:
   ```bash
   echo $AWS_REGION
   # Should be: us-east-1 (or your region)
   ```

3. **Check DynamoDB permissions**:
   - You need `dynamodb:CreateTable`, `dynamodb:DescribeTable`, `dynamodb:PutItem`, `dynamodb:Query`, `dynamodb:Scan` permissions

### Check server logs:

When you add a plant, check your server logs for:
- `✅ Created in-app notification for new planting: <notification_id>`
- `⚠️ save_notification returned None` (means table doesn't exist)
- `❌ Notifications table 'notifications' does not exist in DynamoDB!`

## Manual Table Creation (via AWS Console)

1. Go to AWS Console → DynamoDB
2. Click "Create table"
3. Table name: `notifications`
4. Partition key: `notification_id` (String)
5. Settings: Use default settings
6. Click "Create table"
7. After table is created, go to "Indexes" tab
8. Click "Create index"
   - Index name: `user_id-index`
   - Partition key: `user_id` (String)
   - Click "Create index"

## Environment Variable

You can override the table name using:
```bash
export DYNAMO_NOTIFICATIONS_TABLE=my-notifications-table
```

