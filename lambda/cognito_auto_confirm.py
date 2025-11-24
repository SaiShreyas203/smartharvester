"""
Cognito Pre Sign-up Lambda Trigger

Auto-confirms and auto-verifies new users during sign-up via Cognito Hosted UI.

This Lambda function is triggered before a user is created in Cognito.
It automatically:
- Confirms the user (no manual admin confirmation required)
- Verifies email address if present
- Verifies phone number if present

IAM Permissions Required:
- AWSLambdaBasicExecutionRole (for CloudWatch Logs)

Attach to Cognito User Pool:
- AWS Console → Cognito → User Pools → Your Pool → Triggers → Pre sign-up
"""


def lambda_handler(event, context):
    """
    Cognito Pre Sign-up trigger to auto-confirm and auto-verify users.

    This will:
    - auto-confirm the user (no manual admin confirmation required)
    - auto-verify email and phone attributes when present

    Args:
        event: Cognito trigger event containing user attributes
        context: Lambda context object

    Returns:
        Modified event with auto-confirm/verify settings
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

