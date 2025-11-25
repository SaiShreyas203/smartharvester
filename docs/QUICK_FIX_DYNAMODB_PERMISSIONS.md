# Quick Fix: Add DynamoDB Permissions for Notifications Table

## Problem
The IAM user `django-s3-user` needs DynamoDB permissions for the `notifications` table.

## Solution: Update IAM Policy

### Step 1: Go to AWS Console
1. **IAM** → **Users** → `django-s3-user`
2. **Permissions** tab → Find existing DynamoDB policy → **Edit**

### Step 2: Add Notifications Table
Add these resources to the existing policy:

```json
"arn:aws:dynamodb:us-east-1:518029233624:table/notifications",
"arn:aws:dynamodb:us-east-1:518029233624:table/notifications/index/*"
```

### Step 3: Complete Policy JSON
Use this updated policy (`docs/dynamodb-policy.json`):

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

### Step 4: Apply Changes
1. **Save** the policy
2. **Wait 5-10 seconds** for IAM changes to propagate
3. **Restart your Django service** (if running):
   ```bash
   sudo systemctl restart smartharvester
   ```

### Verify
After updating permissions, try saving a planting again. The errors should disappear.

