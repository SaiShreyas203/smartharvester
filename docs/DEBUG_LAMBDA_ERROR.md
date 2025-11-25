# Debug: Unrecognizable Lambda Output Error

## Immediate Steps to Debug

### Step 1: Check CloudWatch Logs

The error message "Unrecognizable lambda output" doesn't tell us what's wrong. We need to check CloudWatch logs.

1. **Go to AWS Console** → **CloudWatch** → **Log groups**
2. **Find these log groups:**
   - `/aws/lambda/cognito-auto-confirm` (Pre Sign-up trigger)
   - `/aws/lambda/post-confirmation` (Post Confirmation trigger)
3. **Check the most recent log stream** after a failed signup attempt
4. **Look for:**
   - Error messages
   - Exception stack traces
   - Any lines with "ERROR" or "Exception"

### Step 2: Verify Lambda Functions Are Deployed

Make sure the updated Lambda functions are actually deployed in AWS:

1. **Go to AWS Console** → **Lambda** → **Functions**
2. **Find your Lambda functions:**
   - `cognito-auto-confirm` (Pre Sign-up)
   - `post-confirmation` (Post Confirmation)
3. **Check:**
   - Do they exist?
   - Is the code updated?
   - Are they attached to your Cognito User Pool?

### Step 3: Check Lambda Function Attachments

1. **Go to AWS Console** → **Cognito** → **User Pools** → Your User Pool
2. **Go to** → **Sign-up experience** tab → **Triggers** section
3. **Verify:**
   - Pre sign-up trigger → Should have `cognito-auto-confirm` Lambda
   - Post confirmation trigger → Should have `post-confirmation` Lambda
   - If missing, attach them

### Step 4: Check Lambda Environment Variables

1. **Go to Lambda function** → **Configuration** → **Environment variables**
2. **Verify Post Confirmation Lambda has:**
   - `DYNAMO_USERS_TABLE` = `users`
   - `DYNAMO_USERS_PK` = `username`
   - `AWS_REGION` = `us-east-1`
3. **If missing, add them**

### Step 5: Check Lambda Permissions

1. **Go to Lambda function** → **Configuration** → **Permissions**
2. **Check Execution role** has:
   - CloudWatch Logs permissions
   - DynamoDB PutItem permissions (for Post Confirmation Lambda)

### Step 6: Test Lambda Function Manually

You can test the Lambda function directly in AWS Console:

1. **Go to Lambda function** → **Test** tab
2. **Create a test event** using Cognito trigger event format
3. **Run the test** and check for errors

## Common Issues and Fixes

### Issue 1: Lambda Not Deployed

**Symptom:** CloudWatch logs show old code or no recent executions

**Fix:** Deploy the updated Lambda code to AWS

### Issue 2: Lambda Not Attached to Cognito

**Symptom:** Lambda exists but isn't triggered during signup

**Fix:** Attach Lambda to Cognito User Pool triggers

### Issue 3: Environment Variables Missing

**Symptom:** CloudWatch logs show "DYNAMO_USERS_TABLE not configured"

**Fix:** Add environment variables to Lambda function

### Issue 4: Lambda Permissions Missing

**Symptom:** CloudWatch logs show "AccessDenied" or permission errors

**Fix:** Add DynamoDB permissions to Lambda execution role

### Issue 5: Lambda Timeout

**Symptom:** CloudWatch logs show timeout errors

**Fix:** Increase Lambda timeout (Configuration → General → Timeout → 10 seconds)

## Quick Test: Temporarily Disable Lambda

To isolate the issue, you can temporarily disable the Lambda triggers:

1. **Go to Cognito** → **User Pools** → Your Pool → **Sign-up experience** → **Triggers**
2. **Remove the Lambda functions** from triggers (set to "None")
3. **Try signing up** - if it works, the issue is with the Lambda
4. **Re-attach and fix the Lambda** before re-enabling

## Need to See Actual Error?

Please check CloudWatch logs and share:
1. The error message from CloudWatch
2. The Lambda function name that's failing
3. Any stack trace shown in logs

This will help identify the exact issue.

