# Fix DynamoDB Access Denied Errors

## The Problem

You're seeing:
```
AccessDeniedException: User: arn:aws:iam::518029233624:user/django-s3-user is not authorized to perform: dynamodb:Scan on resource: arn:aws:dynamodb:us-east-1:518029233624:table/plantings
```

This means your IAM user `django-s3-user` doesn't have DynamoDB permissions.

## Solution: Add DynamoDB Permissions to IAM User

### Option 1: Add DynamoDB Permissions via AWS Console

1. **Go to AWS Console** → **IAM** → **Users** → `django-s3-user`

2. **Click "Add permissions"** → **Attach policies directly**

3. **Search for and attach:**
   - `AmazonDynamoDBFullAccess` (for full access)
   - OR create a custom policy with minimal permissions (see below)

4. **Click "Next"** → **Add permissions**

### Option 2: Create Custom IAM Policy (Recommended)

Create a policy with only the permissions needed:

1. **Go to IAM** → **Policies** → **Create policy**

2. **Use JSON editor** and paste:

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
                "arn:aws:dynamodb:us-east-1:518029233624:table/users/index/*"
            ]
        }
    ]
}
```

3. **Name it**: `DynamoDBPlantingsUsersAccess`

4. **Attach to user**: Go to `django-s3-user` → **Add permissions** → **Attach policies directly** → Select the policy

### Option 3: Use AWS CLI

```bash
# Create the policy
aws iam create-policy \
    --policy-name DynamoDBPlantingsUsersAccess \
    --policy-document file://dynamodb-policy.json

# Attach to user
aws iam attach-user-policy \
    --user-name django-s3-user \
    --policy-arn arn:aws:iam::518029233624:policy/DynamoDBPlantingsUsersAccess
```

## Required Permissions

Your IAM user needs these DynamoDB permissions:

- **GetItem** - Read single items
- **PutItem** - Create/update items
- **UpdateItem** - Update existing items
- **DeleteItem** - Delete items
- **Query** - Query by partition key or GSI (more efficient than Scan)
- **Scan** - Scan entire table (fallback, less efficient)

## Verify Permissions

After adding permissions:

1. **Wait a few seconds** for IAM changes to propagate

2. **Test by restarting the service:**
   ```bash
   sudo systemctl restart smartharvester
   ```

3. **Check logs:**
   ```bash
   sudo journalctl -u smartharvester -f
   ```

4. **Should see:**
   - No more `AccessDeniedException` errors
   - Plantings loading successfully
   - `Loaded X plantings from DynamoDB` messages

## Alternative: Use IAM Role Instead of User

For better security, consider using an IAM role instead of access keys:

1. **Create IAM Role** with DynamoDB permissions
2. **Attach role to EC2 instance** (if running on EC2)
3. **Remove access keys** from environment variables
4. **boto3 will automatically use the role**

## Minimal Policy (Most Secure)

If you want minimal permissions, use this policy:

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
                "dynamodb:Query"
            ],
            "Resource": [
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings/index/user_id-index",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users/index/*"
            ]
        }
    ]
}
```

**Note**: This removes `Scan` permission. The app will use `Query` instead (more efficient). If your GSI doesn't exist, you'll need to either:
- Create the GSI (`user_id-index` on plantings table)
- Or add `Scan` permission back

## Quick Fix (Temporary)

If you need a quick fix for testing:

1. **Attach `AmazonDynamoDBFullAccess`** to `django-s3-user`
2. **Restart service**
3. **Test**
4. **Then create a more restrictive policy** for production

## After Fixing Permissions

The app should:
- ✅ Load plantings from DynamoDB without errors
- ✅ Save plantings to DynamoDB successfully
- ✅ Query user notifications without errors
- ✅ No more `AccessDeniedException` in logs

