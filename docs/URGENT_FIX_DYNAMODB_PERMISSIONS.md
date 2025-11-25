# URGENT: Fix DynamoDB AccessDeniedException Errors

## Problem
You're seeing multiple `AccessDeniedException` errors because the IAM user `django-s3-user` doesn't have DynamoDB permissions.

**Errors:**
- Cannot `Scan` `plantings` table
- Cannot `Scan` `users` table
- Cannot `PutItem` on `plantings` table
- Cannot `PutItem` on `notifications` table

## Quick Fix: Add DynamoDB Permissions

### Step 1: Go to AWS Console
1. Open **AWS Console** → **IAM** → **Users**
2. Click on `django-s3-user`
3. Go to **Permissions** tab

### Step 2: Add/Edit Policy
**Option A: If you already have a DynamoDB policy**
1. Find the existing DynamoDB policy
2. Click **Edit**
3. Use the JSON below and **Save**

**Option B: If no DynamoDB policy exists**
1. Click **Add permissions** → **Attach policies directly**
2. Click **Create policy**
3. Switch to **JSON** tab
4. Paste the policy below
5. Name it: `DynamoDBFullAccess`
6. **Create policy**
7. Go back to user → **Add permissions** → Attach the policy you just created

### Step 3: Policy JSON

Use this policy (already includes `notifications` table):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings/index/*",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users/index/*",
                "arn:aws:dynamodb:us-east-1:518029233624:table/notifications",
                "arn:aws:dynamodb:us-east-1:518029233624:table/notifications/index/*"
            ]
        }
    ]
}
```

### Step 4: Verify
1. **Save** the policy
2. **Wait 10-15 seconds** for IAM to propagate
3. Try saving a planting again - the errors should be gone

## Quick Test (After Adding Permissions)

```bash
# Test if permissions are working
python3 -c "
import boto3
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('plantings')
try:
    table.scan(Limit=1)
    print('✅ DynamoDB permissions are working!')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

## Alternative: Use AWS CLI

If you have AWS CLI configured:

```bash
# Create policy from file
aws iam create-policy \
    --policy-name DynamoDBPlantingsUsersNotificationsAccess \
    --policy-document file://docs/dynamodb-policy.json

# Get the policy ARN from output, then attach to user
aws iam attach-user-policy \
    --user-name django-s3-user \
    --policy-arn arn:aws:iam::518029233624:policy/DynamoDBPlantingsUsersNotificationsAccess
```

## After Fixing Permissions

The errors will stop and you'll see:
- ✅ Plantings saving to DynamoDB successfully
- ✅ Notifications saving to DynamoDB successfully
- ✅ No more `AccessDeniedException` errors in logs

