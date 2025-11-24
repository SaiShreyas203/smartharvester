# SNS Notification Flow Analysis

## How SNS Topics Work

**SNS Topics are broadcast mechanisms:**
- When you publish ONE message to a topic, ALL confirmed subscribers receive it
- This is different from direct email sending (SES) where you send to one recipient

## Current Implementation

### 1. Lambda Function (`lambda/notification_lambda.py`)

**Flow:**
```python
1. Scan ALL users from DynamoDB users table
2. For each user with email:
   - Build personalized message
   - Publish to SNS topic: arn:aws:sns:us-east-1:518029233624:harvest-notifications
   - Result: ALL subscribers receive each message
```

**Issue:** If you have 10 users, it publishes 10 times to the topic, and all 10 subscribers get 10 emails (one for each user).

### 2. Django Code (`tracker/views.py` - `save_planting`)

**Flow:**
```python
1. User adds/edits plant
2. Get user's email from:
   - request.cognito_payload.get('email')
   - get_user_data_from_token(request)
   - request.user.email (Django auth)
   - DynamoDB users table (fallback)
3. Ensure email is subscribed to SNS topic
4. Publish ONE message to SNS topic
5. Result: ALL confirmed subscribers receive the message
```

**Current Code Location:**
- `save_planting()` function: Lines 982-1100
- `update_planting()` function: Lines 1320-1446

## The Problem

When you add a plant:
1. ✅ Code retrieves your email
2. ✅ Code checks subscription status
3. ✅ Code publishes to SNS topic
4. ❌ **But you don't receive email**

## Why This Happens

**SNS Topic Behavior:**
- Publishing to a topic sends to ALL subscribers
- If subscription is "PendingConfirmation", emails won't be delivered
- If publish fails silently, you won't know

## Debug Checklist

### Check 1: Is email being retrieved?
Look for log: `save_planting: Found email from ...`

### Check 2: Is subscription confirmed?
Look for log: `save_planting: Email ... subscription status: ...`
- Should NOT be "PendingConfirmation"
- Should be a full ARN like `arn:aws:sns:us-east-1:518029233624:harvest-notifications:7cb2cdc6-...`

### Check 3: Is publish succeeding?
Look for log: `✅ Sent SNS notification email for new planting to topic ... (MessageId: ...)`

### Check 4: Is code path being executed?
The notification code is wrapped in try/except and won't fail the request if it fails.

## Next Steps to Fix

1. **Add more aggressive logging** to see exactly where it fails
2. **Verify email retrieval** from Cognito token
3. **Check AWS CloudWatch** for SNS publish errors
4. **Test with a simple publish** to verify SNS is working

