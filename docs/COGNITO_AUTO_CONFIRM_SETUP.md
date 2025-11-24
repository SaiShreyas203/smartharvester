# Cognito Auto-Confirm Setup

This guide shows how to set up automatic user confirmation and email/phone verification for Cognito sign-ups using a Pre Sign-up Lambda trigger.

## What This Does

When users sign up via the Cognito Hosted UI, they will be:
- ✅ **Auto-confirmed** - No manual admin approval needed
- ✅ **Email auto-verified** - Email address is marked as verified automatically
- ✅ **Phone auto-verified** - Phone number is marked as verified automatically (if provided)

## Step-by-Step Setup

### Step 1: Create the Lambda Function

1. **Go to AWS Console** → **Lambda** → **Create function**

2. **Choose "Author from scratch"**

3. **Configure:**
   - **Function name**: `cognito-auto-confirm` (or any name you prefer)
   - **Runtime**: `Python 3.9` or `Python 3.10`
   - **Architecture**: `x86_64`
   - **Execution role**: Choose "Create a new role with basic Lambda permissions"
     - This will create a role with `AWSLambdaBasicExecutionRole` which allows CloudWatch Logs

4. **Click "Create function"**

### Step 2: Add the Code

1. **In the Lambda function editor**, replace the default code with:

```python
def lambda_handler(event, context):
    """
    Cognito Pre Sign-up trigger to auto-confirm and auto-verify users.
    """
    # Ensure response object exists
    response = event.setdefault("response", {})

    # Auto-confirm the user
    response["autoConfirmUser"] = True

    # If email is present, auto-verify it
    if "request" in event and "userAttributes" in event["request"]:
        attrs = event["request"]["userAttributes"]
        if attrs.get("email"):
            response["autoVerifyEmail"] = True
        if attrs.get("phone_number"):
            response["autoVerifyPhone"] = True

    return event
```

2. **Or use the file**: Copy the code from `lambda/cognito_auto_confirm.py`

3. **Click "Deploy"** to save

### Step 3: Grant Cognito Permission to Invoke Lambda

1. **In the Lambda function**, go to **Configuration** → **Permissions**

2. **Click on the Execution role** (it will open IAM)

3. **Add an inline policy** with this JSON:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": "arn:aws:lambda:REGION:ACCOUNT_ID:function:cognito-auto-confirm"
        }
    ]
}
```

**Replace:**
- `REGION` with your AWS region (e.g., `us-east-1`)
- `ACCOUNT_ID` with your AWS account ID
- `cognito-auto-confirm` with your Lambda function name if different

**OR** use the simpler method below:

### Alternative: Grant Permission from Cognito Side

1. **Go to Cognito** → **User Pools** → **Your Pool** → **Triggers**

2. **Select the Lambda function** in the Pre sign-up dropdown

3. **AWS will automatically prompt** to grant Cognito permission to invoke the Lambda

4. **Click "Grant"** when prompted

### Step 4: Attach Lambda to Cognito User Pool

1. **Go to AWS Console** → **Cognito** → **User Pools**

2. **Select your User Pool** (e.g., the one with ID `us-east-1_HGEM2vRNI`)

3. **Navigate to**: **Sign-up experience** → **Triggers** (or **App integration** → **Triggers**)

4. **Find "Pre sign-up" trigger**

5. **Select your Lambda function** from the dropdown (e.g., `cognito-auto-confirm`)

6. **Click "Save changes"**

### Step 5: Verify Hosted UI Configuration

Ensure your Cognito App Client is configured correctly:

1. **Go to**: **App integration** → **App client settings**

2. **Verify:**
   - ✅ **Allowed OAuth flows**: Authorization code grant (and/or Implicit grant)
   - ✅ **Allowed callback URLs**: Includes `https://3.235.196.246.nip.io/auth/callback/`
   - ✅ **Allowed sign-out URLs**: Includes `https://3.235.196.246.nip.io/logout/`
   - ✅ **Allowed OAuth scopes**: `openid`, `email`, `profile` (as needed)

3. **Save changes** if you made any

## Testing

### Test 1: Sign Up a New User

1. **Visit your login page**: `https://3.235.196.246.nip.io/auth/login/`

2. **Click "Sign up"** (if available) or use the Hosted UI sign-up link

3. **Fill in the sign-up form:**
   - Email address
   - Password
   - Any other required fields

4. **Submit the form**

5. **Expected result:**
   - User is created and **immediately confirmed**
   - Email is **automatically verified**
   - User can **immediately log in** (no email verification step)

### Test 2: Check Lambda Logs

1. **Go to Lambda** → **Your function** → **Monitor** → **View CloudWatch logs**

2. **Look for invocations** when users sign up

3. **Check the event structure** to see what data Cognito sends

### Test 3: Verify User in Cognito Console

1. **Go to Cognito** → **User Pools** → **Your Pool** → **Users**

2. **Find the newly created user**

3. **Check status:**
   - ✅ **Status**: Should be "Confirmed" (not "Unconfirmed")
   - ✅ **Email verified**: Should be "Verified" (green checkmark)
   - ✅ **Phone verified**: Should be "Verified" if phone was provided

## Security Considerations

### ⚠️ Important Notes

1. **Email Verification Bypass**: This automatically verifies emails without sending verification codes. Only use this if:
   - You trust the email addresses (e.g., internal users)
   - You have other verification mechanisms
   - You're in a development/testing environment

2. **Production Use**: For production, consider:
   - Keeping email verification enabled (remove `autoVerifyEmail`)
   - Using a custom email verification flow
   - Adding additional validation in the Lambda

3. **Phone Verification**: Auto-verifying phone numbers bypasses SMS verification. Use with caution.

### Recommended: Conditional Auto-Verify

You can modify the Lambda to conditionally verify based on domain or other criteria:

```python
def lambda_handler(event, context):
    response = event.setdefault("response", {})
    response["autoConfirmUser"] = True

    if "request" in event and "userAttributes" in event["request"]:
        attrs = event["request"]["userAttributes"]
        email = attrs.get("email", "")
        
        # Only auto-verify emails from trusted domains
        trusted_domains = ["yourcompany.com", "example.com"]
        if email and any(email.endswith(f"@{domain}") for domain in trusted_domains):
            response["autoVerifyEmail"] = True
        # Otherwise, require email verification
        
        if attrs.get("phone_number"):
            response["autoVerifyPhone"] = True

    return event
```

## Troubleshooting

### Lambda Not Being Invoked

1. **Check Lambda permissions**: Ensure Cognito has permission to invoke the function
2. **Check trigger configuration**: Verify the Lambda is selected in Pre sign-up trigger
3. **Check Lambda logs**: Look for errors in CloudWatch Logs

### Users Still Not Auto-Confirmed

1. **Check Lambda response**: Ensure the function returns the event with `autoConfirmUser: true`
2. **Check Lambda logs**: Look for any errors or exceptions
3. **Verify trigger is attached**: Double-check the Pre sign-up trigger is set

### Email Not Auto-Verified

1. **Check user attributes**: Ensure email is present in `event.request.userAttributes.email`
2. **Check Lambda code**: Verify `autoVerifyEmail` is set to `True`
3. **Check Lambda logs**: Look for the event structure

## Lambda Function Code

The complete code is in `lambda/cognito_auto_confirm.py`. You can:

1. **Copy it directly** into the Lambda editor
2. **Deploy via AWS CLI** (if you have it set up)
3. **Use as reference** for custom modifications

## Next Steps

After setting this up:

1. ✅ New sign-ups will be auto-confirmed
2. ✅ Users can log in immediately after sign-up
3. ✅ No email verification step required
4. ✅ Test with a new user sign-up

## Rollback

If you need to disable auto-confirmation:

1. **Go to Cognito** → **User Pools** → **Your Pool** → **Triggers**
2. **Remove the Lambda** from Pre sign-up trigger (set to "None")
3. **Save changes**

Users will then need manual confirmation or email verification as before.

