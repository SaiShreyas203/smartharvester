# Immediate Fix: "Unrecognizable lambda output" Error

## Quick Diagnosis

The error persists because the **updated Lambda code needs to be deployed to AWS**. The fixes we made are only in your local code - AWS is still running the old Lambda code.

## Step 1: Check Current Status

Run this to see what's deployed:

```bash
python scripts/check_lambda_deployment.py
```

This will show:
- ✅/❌ If Lambda functions exist
- ✅/❌ If they're attached to Cognito
- ✅/❌ Environment variables configured

## Step 2: Quick Fix Options

### Option A: Temporarily Disable Lambda Triggers (Fastest)

**This allows signup to work immediately while we fix the Lambda:**

1. **Go to AWS Console** → **Cognito** → **User Pools** → Your User Pool
2. **Go to** → **Sign-up experience** tab → **Lambda triggers** section
3. **Remove Lambda functions:**
   - **Pre sign-up**: Set to "None" (temporarily)
   - **Post confirmation**: Set to "None" (temporarily)
4. **Save changes**
5. **Try signing up again** - should work now

**Note:** This means users won't be auto-confirmed or saved to DynamoDB automatically, but signup will work. You can re-attach the Lambdas after fixing them.

### Option B: Deploy Fixed Lambda Code (Proper Fix)

**Update the Lambda functions in AWS with the fixed code:**

#### Method 1: AWS Console (Easiest)

1. **Go to AWS Console** → **Lambda** → **Functions**

2. **For Post Confirmation Lambda:**
   - Find/create function: `post-confirmation`
   - Go to **Code** tab
   - Copy code from `lambda/post_confirmation_lambda.py`
   - Paste into code editor
   - Click **Deploy**

3. **For Pre Sign-up Lambda:**
   - Find/create function: `cognito-auto-confirm`
   - Go to **Code** tab
   - Copy code from `lambda/cognito_auto_confirm.py`
   - Paste into code editor
   - Click **Deploy**

4. **Set Environment Variables** (for Post Confirmation Lambda):
   - Go to **Configuration** → **Environment variables**
   - Add:
     - `DYNAMO_USERS_TABLE` = `users`
     - `DYNAMO_USERS_PK` = `username`
     - `AWS_REGION` = `us-east-1`

5. **Attach to Cognito:**
   - Go to **Cognito** → **User Pools** → Your Pool → **Sign-up experience** → **Triggers**
   - Attach `cognito-auto-confirm` to **Pre sign-up**
   - Attach `post-confirmation` to **Post confirmation**

6. **Test signup again**

#### Method 2: AWS CLI

```bash
# Navigate to lambda directory
cd lambda

# Update Post Confirmation Lambda
zip post_confirmation_lambda.zip post_confirmation_lambda.py
aws lambda update-function-code \
    --function-name post-confirmation \
    --zip-file fileb://post_confirmation_lambda.zip \
    --region us-east-1

# Update Pre Sign-up Lambda
zip cognito_auto_confirm.zip cognito_auto_confirm.py
aws lambda update-function-code \
    --function-name cognito-auto-confirm \
    --zip-file fileb://cognito_auto_confirm.zip \
    --region us-east-1

# Set environment variables for Post Confirmation Lambda
aws lambda update-function-configuration \
    --function-name post-confirmation \
    --environment Variables="{DYNAMO_USERS_TABLE=users,DYNAMO_USERS_PK=username,AWS_REGION=us-east-1}" \
    --region us-east-1
```

## Step 3: Check CloudWatch Logs

After deploying, check what's actually happening:

1. **Go to AWS Console** → **CloudWatch** → **Log groups**
2. **Find:**
   - `/aws/lambda/cognito-auto-confirm`
   - `/aws/lambda/post-confirmation`
3. **Check recent log streams** after a signup attempt
4. **Look for error messages**

## What to Share for Further Help

If the error persists after deployment, please share:

1. **CloudWatch log output** from the Lambda function that's failing
2. **Lambda function name** (Pre Sign-up or Post Confirmation)
3. **Error message** from CloudWatch logs (not just "Unrecognizable lambda output")

This will help identify the exact issue.

## Quick Checklist

- [ ] Updated Lambda code deployed to AWS
- [ ] Environment variables set in Lambda Configuration
- [ ] Lambda functions attached to Cognito User Pool triggers
- [ ] Lambda timeout set to at least 10 seconds
- [ ] Lambda has DynamoDB permissions (for Post Confirmation)
- [ ] Checked CloudWatch logs for actual error

