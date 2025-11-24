# SNS Notification Debug Guide

## Current SNS Flow

### Lambda Function (`lambda/notification_lambda.py`)
1. Scans ALL users from DynamoDB `users` table
2. For EACH user with email:
   - Builds a personalized message
   - Publishes to SNS topic `arn:aws:sns:us-east-1:518029233624:harvest-notifications`
   - **Issue**: Each publish goes to ALL subscribers, so if 10 users, all get 10 emails

### Django Code (`tracker/views.py` - `save_planting`)
1. When user adds a plant:
   - Retrieves user's email (from Cognito payload, token, Django user, or DynamoDB)
   - Checks/ensures email is subscribed to SNS topic
   - Publishes ONE message to SNS topic
   - Message goes to ALL confirmed subscribers

## How SNS Topics Work

- **SNS Topics broadcast to ALL subscribers**
- When you publish ONE message, ALL confirmed email subscribers receive it
- This is different from direct email (SES) which sends to one recipient

## Current Issue

When you add a plant, the notification might not be sent because:
1. Email not found in request
2. Publish is failing
3. Code path not being executed

## Debug Steps

### 1. Check Server Logs
When you add a plant, look for these log messages:
```
save_planting: Found email from ...
save_planting: Sending SNS notification to ...
✅ Sent SNS notification email for new planting to topic ... (MessageId: ...)
```

If you see:
- `⚠️ No email found for user` → Email retrieval failed
- `❌ Failed to send SNS notification` → Publish failed
- No log messages at all → Code not being executed

### 2. Verify Email Retrieval
The code tries these sources in order:
1. `request.cognito_payload.get('email')`
2. `get_user_data_from_token(request).get('email')`
3. `request.user.email` (Django auth)
4. DynamoDB users table (by username or user_id)

### 3. Verify SNS Configuration
- Check `config/settings.py`: `SNS_TOPIC_ARN` should be set
- Topic ARN: `arn:aws:sns:us-east-1:518029233624:harvest-notifications`
- Email subscription status: Should be "Confirmed" (not "PendingConfirmation")

## How to Test

1. Add a plant and check logs immediately
2. Look for the specific log messages above
3. If email is found but publish fails, check AWS CloudWatch logs or SNS topic metrics
4. Verify the email subscription is confirmed in AWS SNS console

