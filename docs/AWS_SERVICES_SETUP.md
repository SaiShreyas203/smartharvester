# AWS Services Setup Guide

This guide walks you through setting up all AWS services required for SmartHarvester according to the architecture.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured (`aws configure`)
3. **Python 3.10+** for Lambda functions
4. **Boto3** installed (`pip install boto3`)

## Quick Setup

Run the automated setup script:

```bash
chmod +x scripts/setup_aws_services.sh
./scripts/setup_aws_services.sh
```

This will create:
- DynamoDB tables (`users`, `plantings`)
- S3 bucket (`terratrack-media`)
- SNS topic (`harvest-notifications`)

## Manual Setup Steps

### 1. DynamoDB Tables

#### Create `users` table:
```bash
aws dynamodb create-table \
    --table-name users \
    --attribute-definitions AttributeName=username,AttributeType=S \
    --key-schema AttributeName=username,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

#### Create `plantings` table:
```bash
aws dynamodb create-table \
    --table-name plantings \
    --attribute-definitions AttributeName=planting_id,AttributeType=S AttributeName=user_id,AttributeType=S \
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

### 2. S3 Bucket

```bash
# Create bucket
aws s3api create-bucket \
    --bucket terratrack-media \
    --region us-east-1

# Set bucket policy for public read access to media files
cat > bucket-policy.json <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::terratrack-media/media/*"
        }
    ]
}
EOF

aws s3api put-bucket-policy --bucket terratrack-media --policy file://bucket-policy.json
```

### 3. SNS Topic

```bash
aws sns create-topic \
    --name harvest-notifications \
    --region us-east-1
```

Note the Topic ARN (e.g., `arn:aws:sns:us-east-1:518029233624:harvest-notifications`)

### 4. Cognito User Pool

Already configured:
- User Pool ID: `us-east-1_HGEM2vRNI`
- Domain: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
- App Client ID: `4l8j19f73h5hqmlldgc6jigk3k`

### 5. Lambda Functions

#### Deploy Cognito Triggers:

```bash
# Use the deployment script
chmod +x scripts/deploy_cognito_lambda.sh
./scripts/deploy_cognito_lambda.sh
```

Or manually:

```bash
# Package and deploy Pre Sign-up trigger
cd lambda
zip cognito_auto_confirm.zip cognito_auto_confirm.py
aws lambda create-function \
    --function-name cognito-auto-confirm \
    --runtime python3.10 \
    --role arn:aws:iam::518029233624:role/lambda-execution-role \
    --handler cognito_auto_confirm.lambda_handler \
    --zip-file fileb://cognito_auto_confirm.zip \
    --region us-east-1

# Package and deploy Post Confirmation trigger
zip post_confirmation_lambda.zip post_confirmation_lambda.py
aws lambda create-function \
    --function-name post-confirmation \
    --runtime python3.10 \
    --role arn:aws:iam::518029233624:role/lambda-execution-role \
    --handler post_confirmation_lambda.lambda_handler \
    --zip-file fileb://post_confirmation_lambda.zip \
    --environment Variables="{DYNAMO_USERS_TABLE=users,DYNAMO_USERS_PK=username}" \
    --region us-east-1
```

#### Attach to Cognito:

```bash
# Attach Pre Sign-up trigger
aws cognito-idp update-user-pool \
    --user-pool-id us-east-1_HGEM2vRNI \
    --lambda-config PreSignUp=arn:aws:lambda:us-east-1:518029233624:function:cognito-auto-confirm \
    --region us-east-1

# Attach Post Confirmation trigger
aws cognito-idp update-user-pool \
    --user-pool-id us-east-1_HGEM2vRNI \
    --lambda-config PostConfirmation=arn:aws:lambda:us-east-1:518029233624:function:post-confirmation \
    --region us-east-1
```

### 6. RDS PostgreSQL

Use CloudFormation template:

```bash
aws cloudformation create-stack \
    --stack-name smartharvester-rds \
    --template-body file://infrastructure.yml \
    --parameters \
        ParameterKey=DBMasterUsername,ParameterValue=terratrackadmin \
        ParameterKey=DBMasterPassword,ParameterValue=YourSecurePassword123! \
        ParameterKey=DBName,ParameterValue=terratrackdb \
        ParameterKey=VpcId,ParameterValue=vpc-xxxxx \
        ParameterKey=SubnetIds,ParameterValue=subnet-xxxxx,subnet-yyyyy \
    --region us-east-1
```

Or use AWS Console:
1. Go to CloudFormation → Create Stack
2. Upload `infrastructure.yml`
3. Fill in parameters
4. Create stack

## IAM Permissions

### EC2/Elastic Beanstalk Instance Role

Attach this policy to your EC2 instance role or Elastic Beanstalk environment:

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
                "arn:aws:dynamodb:us-east-1:518029233624:table/users",
                "arn:aws:dynamodb:us-east-1:518029233624:table/users/index/*",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings",
                "arn:aws:dynamodb:us-east-1:518029233624:table/plantings/index/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::terratrack-media/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish",
                "sns:Subscribe"
            ],
            "Resource": "arn:aws:sns:us-east-1:518029233624:harvest-notifications"
        }
    ]
}
```

### Lambda Execution Role

For Cognito triggers:
- `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
- DynamoDB write permissions for `users` table

For notification Lambda:
- DynamoDB read permissions
- SNS publish permissions

## Environment Variables

Set these in your systemd service or Elastic Beanstalk:

```bash
# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# DynamoDB
DYNAMO_USERS_TABLE=users
DYNAMO_PLANTINGS_TABLE=plantings
DYNAMO_USERS_PK=username

# S3
S3_BUCKET=terratrack-media

# SNS
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications

# Cognito
COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
COGNITO_REGION=us-east-1
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/

# RDS (optional)
DATABASE_URL=postgresql://user:password@rds-endpoint:5432/dbname
```

## Verification

Run the verification script to check all services:

```bash
chmod +x scripts/verify_aws_services.sh
./scripts/verify_aws_services.sh
```

This will check:
- ✓ DynamoDB tables exist
- ✓ S3 bucket exists
- ✓ SNS topic exists
- ✓ Cognito User Pool configured
- ✓ Lambda functions deployed
- ✓ RDS instance (optional)

## Troubleshooting

### DynamoDB Access Denied
- Check IAM permissions
- Verify table names match environment variables
- Check region matches

### S3 Upload Fails
- Verify bucket exists
- Check IAM permissions (s3:PutObject)
- Verify bucket policy allows public read

### SNS Notifications Not Working
- Verify topic ARN is correct
- Check email subscription confirmation
- Verify IAM permissions (sns:Publish)

### Lambda Triggers Not Firing
- Check Lambda function exists
- Verify trigger is attached to Cognito User Pool
- Check CloudWatch Logs for errors
- Verify Lambda execution role has correct permissions

## Next Steps

1. ✅ Set up all AWS services (this guide)
2. ✅ Configure environment variables
3. ✅ Deploy Django application
4. ✅ Test authentication flow
5. ✅ Test planting creation
6. ✅ Test image uploads
7. ✅ Test notifications

See `docs/ARCHITECTURE.md` for complete architecture overview.

