# Fix: Elastic Beanstalk Validation Errors

## Errors

1. `ValidationError - No service role specified in buildspec; this is a required argument.`
2. `This branch does not have a default environment`

## Solution

### Fix 1: Remove CodeBuild Integration (Simplest)

The `buildspec.yml` has been updated to remove the `eb_codebuild_settings` section. This makes the buildspec work for standard Elastic Beanstalk deployments without requiring CodeBuild.

**If you want to use CodeBuild later**, you'll need to:
1. Create a CodeBuild service role in IAM
2. Add the role ARN to `buildspec.yml`

For now, the standard buildspec will work fine.

### Fix 2: Create/Set Default Environment

You need to create an environment first:

```bash
# Create a new environment
eb create UrSmartCrop-env

# This will:
# - Create the environment
# - Set it as default
# - Deploy your application
```

**Or if environment already exists:**

```bash
# List environments
eb list

# Set default environment
eb use UrSmartCrop-env

# Or specify environment in commands
eb deploy UrSmartCrop-env
eb setenv UrSmartCrop-env KEY=value
```

## Step-by-Step Setup

### 1. Create Environment

```bash
eb create UrSmartCrop-env
```

This will prompt you for:
- Load balancer type (Application Load Balancer recommended)
- Instance type (t3.micro for testing)
- Key pair (optional, for SSH access)

### 2. Set Environment Variables

After environment is created, set required variables:

```bash
# Cognito
eb setenv COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
eb setenv COGNITO_REGION=us-east-1
eb setenv COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
eb setenv COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k

# Get your EB URL first, then set redirect URI
eb status  # Get the URL
eb setenv COGNITO_REDIRECT_URI=https://your-eb-url.elasticbeanstalk.com/auth/callback/

# AWS Services
eb setenv AWS_REGION=us-east-1
eb setenv DYNAMO_USERS_TABLE=users
eb setenv DYNAMO_PLANTINGS_TABLE=plantings
eb setenv S3_BUCKET=terratrack-media

# Django
eb setenv DJANGO_SECRET_KEY=your-secret-key-here
eb setenv IS_PRODUCTION=True
eb setenv USE_TLS=True
```

**Or set via EB Console:**
1. Go to Elastic Beanstalk → Your Environment
2. Configuration → Software → Environment properties
3. Add all variables

### 3. Configure IAM Instance Role

The EC2 instance needs AWS permissions:

1. Go to EB Console → Your Environment → Configuration
2. Security → IAM instance profile
3. Create/edit role with permissions for:
   - DynamoDB (GetItem, PutItem, Query, Scan)
   - S3 (PutObject, GetObject)
   - SNS (Publish)

See `docs/AWS_SERVICES_SETUP.md` for IAM policy details.

### 4. Deploy

```bash
eb deploy
```

## Alternative: Skip CodeBuild Integration

If you don't need CodeBuild integration, the current `buildspec.yml` (without `eb_codebuild_settings`) will work fine. Elastic Beanstalk will:
- Install dependencies from `requirements.txt`
- Run collectstatic
- Deploy your application

## Verification

After creating environment:

```bash
# Check status
eb status

# View logs
eb logs

# Open in browser
eb open
```

## Common Issues

### Environment Creation Fails

**Check:**
- AWS credentials configured: `aws configure`
- Sufficient IAM permissions
- Region is correct: `us-east-1`

### Environment Variables Not Loading

**Fix:**
- Set in EB Console (more reliable than CLI)
- Restart environment: `eb restart`

### Health Check Fails

**Verify:**
- `/health` endpoint works
- Environment variables are set
- Database connection (if using RDS)

## Next Steps

1. ✅ Fixed `buildspec.yml` (removed CodeBuild requirement)
2. ⏭️ Create environment: `eb create UrSmartCrop-env`
3. ⏭️ Set environment variables
4. ⏭️ Configure IAM permissions
5. ⏭️ Deploy: `eb deploy`
6. ⏭️ Update Cognito redirect URI
7. ⏭️ Test application

The validation errors should now be resolved!

