# SNS Trigger Analysis

## How SNS is Currently Triggered

### 1. Lambda Function (`lambda/notification_lambda.py`)

**Trigger:** CloudWatch Events (Scheduled)

**Flow:**
```python
lambda_handler(event, context):
  1. Scan ALL users from DynamoDB users table
  2. For EACH user with email:
     - Build personalized message
     - Publish to SNS topic
     - ALL subscribers receive the message
```

**Key Points:**
- Publishes ONE message per user
- Each message goes to ALL subscribers
- This is why you receive daily updates

### 2. Django Code (`tracker/views.py`)

**Trigger:** User action (add/edit plant)

**Flow:**
```python
save_planting(request):
  1. Save planting to DynamoDB
  2. Get user's email (Cognito payload, token, Django user, DynamoDB)
  3. Ensure email is subscribed to SNS topic
  4. Publish ONE message to SNS topic
  5. ALL subscribers receive the message
```

**Code Location:**
- `save_planting()`: Lines 982-1100
- `update_planting()`: Lines 1320-1446

## Key Differences

| Aspect | Lambda | Django |
|--------|--------|--------|
| **Trigger** | Scheduled (CloudWatch) | User action |
| **Messages** | One per user | One per action |
| **Delivery** | All subscribers | All subscribers |
| **Personalization** | Per user | Per action |

## Current Issue

**Problem:** Django notifications not being sent/received when adding plants

**Possible Causes:**
1. Email not retrieved from request
2. SNS publish failing silently
3. Subscription not confirmed
4. AWS permissions issue

## Debug Logs Added

The code now logs:
- 🔔 When notification process starts
- 📧 Where email was found
- ✅ When publish succeeds (with MessageId)
- ❌ When publish fails (with error details)

## Next Steps

1. **Test adding a plant** and check server logs
2. **Look for these log messages:**
   - `🔔 SNS Notification: Starting notification process`
   - `save_planting: Found email from ...`
   - `✅ SUCCESS: Sent SNS notification`
   - `❌ FAILED:` or `❌ EXCEPTION:`

3. **If logs show email found but publish fails:**
   - Check AWS credentials
   - Check SNS topic permissions
   - Verify topic ARN is correct

4. **If no logs appear:**
   - Code path not being executed
   - Check if `save_planting()` is being called

