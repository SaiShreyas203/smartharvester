# Lambda Daily Notifications

This Lambda function sends personalized daily email notifications to all users about their upcoming planting tasks and harvests.

## Quick Setup

1. **Copy the code**: Use `scripts/lambda_daily_notifications.py`

2. **Create Lambda function**:
   - Runtime: Python 3.11
   - Timeout: 5 minutes
   - Memory: 256 MB

3. **Set Environment Variables**:
   ```
   DYNAMO_USERS_TABLE=users
   DYNAMO_PLANTINGS_TABLE=plantings
   DYNAMO_USERS_PK=user_id
   SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications
   AWS_REGION=us-east-1
   DAYS_AHEAD=7
   ```

4. **Add IAM Permissions** (see `docs/LAMBDA_SETUP.md` for full policy)

5. **Schedule**: Create EventBridge trigger with `cron(0 9 * * ? *)` (daily at 9 AM UTC)

## Features

✅ Scans all users from DynamoDB  
✅ Gets each user's plantings using GSI query  
✅ Calculates upcoming tasks/harvests using same logic as webapp  
✅ Respects user notification preferences  
✅ Sends personalized emails via SNS  
✅ Handles errors gracefully  

## Full Documentation

See `docs/LAMBDA_SETUP.md` for complete setup instructions.

