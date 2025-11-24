# Fix: Error Saving Plant Details

## Problem

Getting an error when trying to save plant details after filling out the form.

## Common Causes

### 1. DynamoDB Table Doesn't Exist

**Error**: `ResourceNotFoundException` or `Table not found`

**Fix**:
```bash
# Create the plantings table
aws dynamodb create-table \
    --table-name plantings \
    --attribute-definitions \
        AttributeName=planting_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
    --key-schema AttributeName=planting_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --global-secondary-indexes \
        "[{
            \"IndexName\": \"user_id-index\",
            \"KeySchema\": [{\"AttributeName\": \"user_id\", \"KeyType\": \"HASH\"}],
            \"Projection\": {\"ProjectionType\": \"ALL\"}
        }]" \
    --region us-east-1
```

Or use the setup script:
```bash
./scripts/setup_aws_services.sh
```

### 2. Missing IAM Permissions

**Error**: `AccessDeniedException` or `User is not authorized`

**Fix**: Add DynamoDB permissions to your IAM role/user:
- `dynamodb:PutItem`
- `dynamodb:GetItem`
- `dynamodb:Query`
- `dynamodb:Scan`

See `docs/FIX_DYNAMODB_PERMISSIONS.md` for details.

### 3. Missing Required Fields

**Error**: `ValidationException` or function returns `None`

**Check**: Ensure `user_id` and `username` are present in the planting data.

**Fix**: The code now ensures these are set, but check logs if still failing.

### 4. Invalid Data Types

**Error**: `ValidationException` or type conversion errors

**Fix**: The code now properly converts data types for DynamoDB. Check logs for specific type errors.

### 5. S3 Upload Fails

**Error**: Image upload fails silently

**Fix**: 
- Check S3 bucket exists: `aws s3 ls s3://terratrack-media`
- Check IAM permissions: `s3:PutObject`
- Check bucket policy allows uploads

## Debugging Steps

### Step 1: Check Service Logs

```bash
# Check Django service logs
sudo journalctl -u smartharvester -n 100 | grep -i "save_planting\|dynamodb\|error"

# Or if running manually
python manage.py runserver 0.0.0.0:8000
```

Look for:
- `❌ Failed to save planting to DynamoDB`
- `DynamoDB ClientError`
- `AccessDeniedException`
- `ResourceNotFoundException`

### Step 2: Test DynamoDB Connection

```bash
# Test if you can write to DynamoDB
python scripts/debug_save_planting.py
```

This will test the `save_planting_to_dynamodb` function directly.

### Step 3: Verify AWS Configuration

```bash
# Check environment variables
python manage.py shell
>>> from django.conf import settings
>>> print(settings.DYNAMODB_PLANTINGS_TABLE_NAME)
>>> print(settings.AWS_REGION)

# Check AWS credentials
>>> import boto3
>>> sts = boto3.client('sts')
>>> print(sts.get_caller_identity())
```

### Step 4: Check DynamoDB Table

```bash
# Verify table exists
aws dynamodb describe-table --table-name plantings --region us-east-1

# Check table structure
aws dynamodb describe-table --table-name plantings --region us-east-1 --query 'Table.{KeySchema:KeySchema,GSI:GlobalSecondaryIndexes}'
```

### Step 5: Test with Minimal Data

Try saving a planting with minimal data:
- Crop name: "Test"
- Planting date: "2025-01-01"
- No image

If this works, the issue might be with:
- Image upload (S3)
- Plan calculation
- Specific field values

## Enhanced Error Logging

The code now includes enhanced logging:

1. **Before saving**: Logs user_id, username, crop_name
2. **During save**: Logs DynamoDB operation details
3. **On error**: Logs exception type and full traceback
4. **On success**: Confirms planting_id returned

Check logs for these messages to identify where the failure occurs.

## Quick Fixes

### Fix 1: Create Missing Table

```bash
./scripts/setup_aws_services.sh
```

### Fix 2: Add IAM Permissions

See `docs/FIX_DYNAMODB_PERMISSIONS.md`

### Fix 3: Verify Environment Variables

```bash
# Check if DynamoDB table name is set
echo $DYNAMO_PLANTINGS_TABLE
# Should output: plantings

# Check AWS region
echo $AWS_REGION
# Should output: us-east-1
```

### Fix 4: Test DynamoDB Access

```bash
# Test write access
aws dynamodb put-item \
    --table-name plantings \
    --item '{"planting_id":{"S":"test-123"},"user_id":{"S":"test-user"},"username":{"S":"testuser"},"crop_name":{"S":"Test"}}' \
    --region us-east-1
```

If this fails, you have a permissions issue.

## Expected Behavior

When saving a planting:

1. ✅ User authentication checked
2. ✅ Image uploaded to S3 (if provided)
3. ✅ Planting data validated
4. ✅ Plan calculated
5. ✅ Data saved to DynamoDB
6. ✅ Data saved to session (for immediate display)
7. ✅ Redirect to index page

If any step fails, check the logs for the specific error.

## Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `ResourceNotFoundException` | Table doesn't exist | Create table |
| `AccessDeniedException` | Missing IAM permissions | Add permissions |
| `ValidationException` | Invalid data type | Check data conversion |
| `save_planting_to_dynamodb returned None` | Function failed silently | Check logs for exception |
| `Missing required fields` | crop_name or planting_date missing | Check form submission |

## Still Having Issues?

1. **Check full error traceback** in logs
2. **Run debug script**: `python scripts/debug_save_planting.py`
3. **Verify AWS services**: `./scripts/verify_aws_services.sh`
4. **Check network connectivity** to AWS
5. **Verify environment variables** are loaded correctly

The enhanced logging should now provide more details about what's failing.

