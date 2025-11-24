# Elastic Beanstalk Setup Guide

This guide walks you through deploying SmartHarvester to AWS Elastic Beanstalk.

## Prerequisites

1. **AWS CLI** installed and configured
2. **EB CLI** installed: `pip install awsebcli`
3. **AWS Account** with appropriate permissions
4. **Python 3.11** (as specified in `eb init`)

## Initial Setup

### 1. Initialize Elastic Beanstalk

```bash
eb init -r us-east-1 -p python-3.11 UrSmartCrop
```

This creates:
- `.elasticbeanstalk/` directory with configuration
- `buildspec.yml` (updated with CodeBuild integration)

### 2. Create Environment

```bash
# Create a new environment
eb create UrSmartCrop-env

# Or use existing environment
eb use UrSmartCrop-env
```

### 3. Configure Environment Variables

Set these in the EB Console or via CLI:

**Required:**
```bash
# Cognito
eb setenv COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
eb setenv COGNITO_REGION=us-east-1
eb setenv COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
eb setenv COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
eb setenv COGNITO_REDIRECT_URI=https://your-eb-url.elasticbeanstalk.com/auth/callback/

# AWS
eb setenv AWS_REGION=us-east-1
eb setenv AWS_ACCESS_KEY_ID=your-access-key
eb setenv AWS_SECRET_ACCESS_KEY=your-secret-key

# DynamoDB
eb setenv DYNAMO_USERS_TABLE=users
eb setenv DYNAMO_PLANTINGS_TABLE=plantings

# S3
eb setenv S3_BUCKET=terratrack-media

# Django
eb setenv DJANGO_SECRET_KEY=your-secret-key
eb setenv IS_PRODUCTION=True
eb setenv USE_TLS=True
```

**Or set via EB Console:**
1. Go to Elastic Beanstalk → Your Environment → Configuration
2. Software → Environment properties
3. Add all required variables

### 4. Configure IAM Instance Role

The EC2 instance needs permissions for:
- DynamoDB (read/write)
- S3 (read/write)
- SNS (publish)

1. Go to EC2 → IAM Roles
2. Create or edit the role attached to your EB environment
3. Add policies:
   - DynamoDB access (see `docs/AWS_SERVICES_SETUP.md`)
   - S3 access
   - SNS access

Or use the EB Console:
1. Configuration → Security → IAM instance profile
2. Select/create role with required permissions

## Deployment

### Deploy Application

```bash
# Deploy to environment
eb deploy

# Or deploy specific version
eb deploy --version-label v1.0.0
```

### Check Deployment Status

```bash
# Check environment status
eb status

# View logs
eb logs

# Open in browser
eb open
```

## Configuration Files

### `.ebextensions/django.config`
- Configures WSGI path
- Runs migrations and collectstatic on deploy

### `.ebextensions/04_aws_services.config`
- Sets default AWS service environment variables
- Override in EB Console with actual values

### `.ebextensions/03_healthcheck.config`
- Configures health check endpoint (`/health`)

### `buildspec.yml`
- CodeBuild configuration
- Includes `eb_codebuild_settings` header for EB integration
- Runs tests and collects static files

### `.ebignore`
- Files to exclude from deployment
- Reduces deployment package size

## Post-Deployment

### 1. Update Cognito Redirect URI

After deployment, update Cognito callback URL:

1. Go to AWS Cognito → User Pools → Your Pool
2. App integration → App client settings
3. Update "Allowed callback URLs" to include:
   ```
   https://your-eb-url.elasticbeanstalk.com/auth/callback/
   ```

### 2. Verify Services

```bash
# Check if environment is healthy
eb health

# SSH into instance (if needed)
eb ssh

# View application logs
eb logs --all
```

### 3. Test Application

1. Open application URL: `eb open`
2. Test Cognito login
3. Test adding a planting
4. Verify DynamoDB data
5. Verify S3 image uploads

## Troubleshooting

### Buildspec Warning

If you see:
```
WARNING: Beanstalk configuration header 'eb_codebuild_settings' is missing
```

**Fix**: The `buildspec.yml` has been updated with the required header. Redeploy:
```bash
eb deploy
```

### Deployment Fails

**Check logs:**
```bash
eb logs --all
```

**Common issues:**
- Missing environment variables → Set in EB Console
- IAM permissions → Check instance role
- Database connection → Verify RDS endpoint
- Static files → Check collectstatic output

### Health Check Fails

**Verify health endpoint:**
```bash
curl https://your-eb-url.elasticbeanstalk.com/health
```

Should return 200 OK.

### Environment Variables Not Loading

**Check:**
1. EB Console → Configuration → Software → Environment properties
2. Verify variables are set (not just in `.ebextensions`)
3. Restart environment: `eb restart`

## Environment Management

### Create Multiple Environments

```bash
# Production
eb create UrSmartCrop-prod

# Staging
eb create UrSmartCrop-staging
```

### Switch Between Environments

```bash
eb use UrSmartCrop-prod
eb use UrSmartCrop-staging
```

### Terminate Environment

```bash
eb terminate UrSmartCrop-env
```

## CI/CD Integration

The `buildspec.yml` is configured for CodeBuild integration:

1. **Pre-build**: Logs and dependency installation
2. **Install**: Installs Python 3.11 and requirements
3. **Build**: Runs tests and collects static files
4. **Artifacts**: Packages application for deployment

To use CodeBuild:
1. Create CodeBuild project
2. Point to this repository
3. Use `buildspec.yml` as build specification
4. Configure to deploy to Elastic Beanstalk

## Best Practices

1. **Never commit secrets** - Use EB Console for sensitive values
2. **Use IAM roles** - Prefer instance roles over access keys
3. **Monitor logs** - Set up CloudWatch alarms
4. **Health checks** - Ensure `/health` endpoint works
5. **Blue/Green deployments** - Use for zero-downtime updates
6. **Environment variables** - Set in EB Console, not code

## Next Steps

1. ✅ Initialize EB: `eb init`
2. ✅ Create environment: `eb create`
3. ✅ Set environment variables
4. ✅ Configure IAM permissions
5. ✅ Deploy: `eb deploy`
6. ✅ Update Cognito redirect URI
7. ✅ Test application
8. ✅ Monitor logs and metrics

## Resources

- [EB CLI Documentation](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3.html)
- [Django on Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-django.html)
- [Environment Variables](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/environments-cfg-softwaresettings.html)

