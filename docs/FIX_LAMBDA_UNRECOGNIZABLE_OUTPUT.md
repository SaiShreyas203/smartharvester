# Fix: "Unrecognizable lambda output" Error

## Problem

When signing up with a new account via Cognito Hosted UI, you see:
```
Unrecognizable lambda output
```

This error occurs when a Cognito Lambda trigger (Pre Sign-up or Post Confirmation) doesn't return the event object in the expected format, or throws an unhandled exception.

## Root Causes

1. **Lambda function throws an exception** that isn't caught
2. **Lambda function doesn't return the event object** (returns None or wrong format)
3. **Lambda initialization fails** (e.g., trying to access DynamoDB table before it's configured)
4. **Lambda timeout** (function takes too long)
5. **Lambda returns wrong data type** (not a dict/event object)

## Fix Applied

### 1. Post Confirmation Lambda (`lambda/post_confirmation_lambda.py`)

**Changes:**
- ✅ **Lazy initialization**: DynamoDB resources are initialized inside the handler, not at module level
- ✅ **Error handling**: All exceptions are caught, and event is always returned
- ✅ **Graceful degradation**: If DynamoDB save fails, signup still succeeds

**Key improvements:**
```python
# Before: Table initialized at module level (fails if DYNAMO_TABLE is empty)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMO_TABLE)  # ❌ Fails if DYNAMO_TABLE is ""

# After: Lazy initialization inside handler
def _get_table():
    if not DYNAMO_TABLE:
        return None
    # Initialize only when needed
    ...
```

### 2. Pre Sign-up Lambda (`lambda/cognito_auto_confirm.py`)

**Changes:**
- ✅ **Added logging** for debugging
- ✅ **Added exception handling** to ensure event is always returned
- ✅ **Graceful fallback** if any error occurs

## How It Works Now

### Sign-Up Flow

```
User fills signup form
    ↓
Pre Sign-up Lambda Trigger
    → Tries to auto-confirm user
    → ALWAYS returns event (even on error)
    ↓
Cognito creates user
    ↓
Post Confirmation Lambda Trigger
    → Tries to save user to DynamoDB
    → ALWAYS returns event (even if DynamoDB fails)
    ↓
✅ Signup succeeds (even if DynamoDB save fails)
```

### Error Handling Strategy

1. **All exceptions are caught** in try-except blocks
2. **Event is always returned** - Cognito requires this
3. **Errors are logged** to CloudWatch for debugging
4. **Signup never fails** due to Lambda errors (graceful degradation)

## Verification

After deploying the updated Lambda functions:

1. **Check CloudWatch Logs**:
   - Go to AWS Console → CloudWatch → Log groups
   - Find your Lambda function log groups:
     - `/aws/lambda/cognito-auto-confirm` (Pre Sign-up)
     - `/aws/lambda/post-confirmation` (Post Confirmation)
   - Look for errors or success messages

2. **Test Sign-up**:
   - Go to Cognito Hosted UI signup page
   - Create a new account
   - Should succeed without "Unrecognizable lambda output" error

3. **Verify User in DynamoDB**:
   - Check if user was saved to DynamoDB `users` table
   - If not, check CloudWatch logs for errors

## Deployment Steps

### Option 1: Update Lambda Code in AWS Console

1. **Go to AWS Console** → **Lambda** → Your Lambda function
2. **Copy the updated code** from:
   - `lambda/post_confirmation_lambda.py`
   - `lambda/cognito_auto_confirm.py`
3. **Paste into Lambda function code editor**
4. **Click "Deploy"**

### Option 2: Deploy via AWS CLI

```bash
# Package and update Post Confirmation Lambda
cd lambda
zip post_confirmation_lambda.zip post_confirmation_lambda.py
aws lambda update-function-code \
    --function-name post-confirmation \
    --zip-file fileb://post_confirmation_lambda.zip \
    --region us-east-1

# Package and update Pre Sign-up Lambda
zip cognito_auto_confirm.zip cognito_auto_confirm.py
aws lambda update-function-code \
    --function-name cognito-auto-confirm \
    --zip-file fileb://cognito_auto_confirm.zip \
    --region us-east-1
```

## Required Environment Variables

Make sure your Post Confirmation Lambda has these environment variables:

- `DYNAMO_USERS_TABLE` - Name of DynamoDB users table (e.g., "users")
- `DYNAMO_USERS_PK` - Partition key name (e.g., "username")
- `AWS_REGION` - AWS region (e.g., "us-east-1")

**Set in Lambda Console:**
- Configuration → Environment variables

## Common Issues

### Issue 1: Lambda Still Shows Error

**Symptom:** "Unrecognizable lambda output" still appears

**Solution:**
1. Check CloudWatch logs for actual error
2. Verify Lambda function is deployed with updated code
3. Check Lambda function timeout (should be at least 3 seconds)

### Issue 2: User Not Saved to DynamoDB

**Symptom:** Signup succeeds but user not in DynamoDB

**Solution:**
1. Check CloudWatch logs for DynamoDB errors
2. Verify Lambda has DynamoDB permissions:
   - `dynamodb:PutItem` on users table
3. Verify environment variables are set correctly

### Issue 3: Lambda Timeout

**Symptom:** Lambda execution times out

**Solution:**
1. Increase Lambda timeout:
   - Configuration → General configuration → Timeout
   - Set to at least 10 seconds
2. Check if DynamoDB table exists and is accessible

## Testing Checklist

- [ ] Pre Sign-up Lambda deployed with error handling
- [ ] Post Confirmation Lambda deployed with lazy initialization
- [ ] Environment variables configured in Lambda
- [ ] Lambda has DynamoDB permissions
- [ ] Lambda timeout is sufficient (10+ seconds)
- [ ] Test signup - should succeed without errors
- [ ] Check CloudWatch logs - should show success messages
- [ ] Verify user in DynamoDB users table

## Key Takeaway

**Always return the event object from Cognito Lambda triggers**, even if there's an error. Cognito requires the event object to be returned in the expected format. If you don't return it, or return None, Cognito will show "Unrecognizable lambda output" error.

