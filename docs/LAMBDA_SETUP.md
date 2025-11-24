# Lambda Daily Notifications Setup

This Lambda function sends daily email notifications to users about their upcoming planting tasks and harvests.

## Overview

The Lambda function (`scripts/lambda_daily_notifications.py`):
1. Scans all users from DynamoDB `users` table
2. For each user with notifications enabled:
   - Fetches their plantings from DynamoDB `plantings` table
   - Calculates upcoming tasks and harvests using the same logic as the webapp
   - Builds personalized daily update message
   - Publishes to SNS topic for email delivery

## Environment Variables

Set these in Lambda configuration:

```bash
DYNAMO_USERS_TABLE=users
DYNAMO_PLANTINGS_TABLE=plantings
DYNAMO_USERS_PK=user_id
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications
AWS_REGION=us-east-1
DAYS_AHEAD=7              # Check next 7 days for reminders
BATCH_SIZE=25             # Process 25 users at a time
BATCH_PAUSE_SECONDS=0.5   # Pause 0.5s between batches
```

## Deployment Steps

### 1. Create Lambda Function

1. Go to AWS Console → Lambda → Create function
2. Choose:
   - **Runtime**: Python 3.11 (or 3.10)
   - **Architecture**: x86_64
3. Name it: `smartharvester-daily-notifications`

### 2. Upload Code

Copy the code from `scripts/lambda_daily_notifications.py` into the Lambda function editor.

### 3. Set Environment Variables

In Lambda → Configuration → Environment variables, add:
- `DYNAMO_USERS_TABLE` = `users`
- `DYNAMO_PLANTINGS_TABLE` = `plantings`
- `DYNAMO_USERS_PK` = `user_id`
- `SNS_TOPIC_ARN` = `arn:aws:sns:us-east-1:518029233624:harvest-notifications`
- `AWS_REGION` = `us-east-1`
- `DAYS_AHEAD` = `7`
- `BATCH_SIZE` = `25`
- `BATCH_PAUSE_SECONDS` = `0.5`

### 4. Configure IAM Permissions

The Lambda execution role needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:Scan",
                "dynamodb:Query",
                "dynamodb:GetItem"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:518029233624:table/users",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users/*",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings/*",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings/index/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws:sns:us-east-1:518029233624:harvest-notifications"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

### 5. Configure Timeout and Memory

- **Timeout**: 5 minutes (300 seconds) - to handle all users
- **Memory**: 256 MB (sufficient for this workload)

### 6. Create EventBridge (CloudWatch Events) Schedule

1. Go to Lambda → Configuration → Triggers → Add trigger
2. Choose **EventBridge (CloudWatch Events)**
3. Create new rule:
   - **Rule name**: `daily-notifications-schedule`
   - **Rule type**: Schedule expression
   - **Schedule expression**: `cron(0 9 * * ? *)` (runs daily at 9 AM UTC)
   - Or: `rate(1 day)` (runs every day at function creation time)

### 7. Test the Function

1. In Lambda console, click "Test"
2. Create a test event (empty JSON `{}` is fine)
3. Click "Test" to run
4. Check CloudWatch Logs for results

## How It Works

1. **Scan Users**: Reads all users from `users` table
2. **Filter**: Skips users without email or with notifications disabled
3. **Get Plantings**: For each user, queries `plantings` table by `user_id`
4. **Calculate Tasks**: Uses the same crop data and plan calculator logic as webapp
5. **Build Message**: Creates personalized email with upcoming tasks/harvests
6. **Publish**: Sends to SNS topic, which delivers to subscribed emails

## Message Format

```
Hello [User Name],

Here is your SmartHarvester daily update about your plantings:

🌾 UPCOMING HARVESTS:
  • Tomatoes: Harvest due in 3 day(s) (2025-11-27)
  • Carrots: Harvest due today (2025-11-24)

📅 UPCOMING TASKS:
  • Basil: Thin seedlings due in 2 day(s) (2025-11-26)
  • Lettuce: Begin baby-leaf harvest due tomorrow (2025-11-25)

Login to your dashboard to see all your plantings and manage your garden.

Happy gardening!
SmartHarvester Team
```

## Troubleshooting

### Function times out
- Increase timeout to 10 minutes
- Increase `BATCH_PAUSE_SECONDS` to reduce load
- Check DynamoDB read capacity

### No emails received
- Verify SNS topic ARN is correct
- Check that user emails are subscribed and confirmed in SNS
- Check CloudWatch Logs for errors
- Verify IAM permissions for SNS publish

### Missing plantings data
- Check that `user_id` in plantings matches users table
- Verify GSI `user_id-index` exists on plantings table
- Check DynamoDB permissions

### Plan calculation errors
- Verify crop names match exactly (case-sensitive)
- Check planting_date format (YYYY-MM-DD)
- Review CloudWatch Logs for specific errors

## Monitoring

View logs in CloudWatch:
- Log group: `/aws/lambda/smartharvester-daily-notifications`
- Logs show: total users, sent, failed, skipped counts

## Cost Considerations

- Lambda: Free tier includes 1M requests/month
- DynamoDB: Pay per read/write (scans may use read capacity)
- SNS: $0.50 per 1M publish requests (very cheap)
- Total cost: Usually under $1/month for typical usage

