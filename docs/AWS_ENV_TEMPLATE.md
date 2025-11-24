# AWS Environment Variables Template

Complete template for all AWS-related environment variables required for SmartHarvester.

## Complete Environment File

Save this as `/etc/systemd/system/smartharvester.service.d/env.conf` or set in Elastic Beanstalk:

```bash
# ============================================
# AWS CORE CONFIGURATION
# ============================================
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id-here
AWS_SECRET_ACCESS_KEY=your-secret-access-key-here

# ============================================
# COGNITO CONFIGURATION
# ============================================
COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
COGNITO_REGION=us-east-1
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/
COGNITO_LOGOUT_REDIRECT_URI=https://3.235.196.246.nip.io/
COGNITO_SCOPE=openid email
# Optional: only if your Cognito app client has a secret
# COGNITO_CLIENT_SECRET=your-client-secret

# ============================================
# DYNAMODB CONFIGURATION
# ============================================
DYNAMO_USERS_TABLE=users
DYNAMO_PLANTINGS_TABLE=plantings
DYNAMO_USERS_PK=username
# Alternative names (for compatibility)
DYNAMODB_USERS_TABLE_NAME=users
DYNAMODB_PLANTINGS_TABLE_NAME=plantings

# ============================================
# S3 CONFIGURATION
# ============================================
S3_BUCKET=terratrack-media
AWS_STORAGE_BUCKET_NAME=terratrack-media
AWS_S3_REGION_NAME=us-east-1

# ============================================
# SNS CONFIGURATION
# ============================================
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications

# ============================================
# RDS CONFIGURATION (Optional)
# ============================================
# Use DATABASE_URL for production (recommended)
# DATABASE_URL=postgresql://username:password@rds-endpoint:5432/dbname

# OR use individual variables
# DATABASE_NAME=terratrackdb
# DATABASE_USER=terratrackadmin
# DATABASE_PASSWORD=your-secure-password
# DATABASE_HOST=rds-endpoint.amazonaws.com
# DATABASE_PORT=5432

# ============================================
# DJANGO CONFIGURATION
# ============================================
DJANGO_SECRET_KEY=your-django-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings
IS_PRODUCTION=False
USE_TLS=True

# ============================================
# CSRF CONFIGURATION
# ============================================
DJANGO_CSRF_TRUSTED_ORIGINS=https://3.235.196.246.nip.io
```

## Variable Descriptions

### AWS Core
- **AWS_REGION**: AWS region for all services (default: `us-east-1`)
- **AWS_ACCESS_KEY_ID**: AWS access key (or use IAM instance role)
- **AWS_SECRET_ACCESS_KEY**: AWS secret key (or use IAM instance role)

### Cognito
- **COGNITO_USER_POOL_ID**: Cognito User Pool ID
- **COGNITO_REGION**: AWS region for Cognito
- **COGNITO_DOMAIN**: Cognito Hosted UI domain
- **COGNITO_CLIENT_ID**: Cognito App Client ID
- **COGNITO_REDIRECT_URI**: OAuth callback URL
- **COGNITO_LOGOUT_REDIRECT_URI**: Logout redirect URL
- **COGNITO_SCOPE**: OAuth scopes (default: `openid email`)
- **COGNITO_CLIENT_SECRET**: Optional, only if app client has secret

### DynamoDB
- **DYNAMO_USERS_TABLE**: Users table name (default: `users`)
- **DYNAMO_PLANTINGS_TABLE**: Plantings table name (default: `plantings`)
- **DYNAMO_USERS_PK**: Primary key for users table (default: `username`)

### S3
- **S3_BUCKET**: S3 bucket name for images (default: `terratrack-media`)
- **AWS_STORAGE_BUCKET_NAME**: Alternative name for S3 bucket
- **AWS_S3_REGION_NAME**: S3 region (defaults to AWS_REGION)

### SNS
- **SNS_TOPIC_ARN**: SNS topic ARN for notifications

### RDS
- **DATABASE_URL**: PostgreSQL connection string (recommended)
- **DATABASE_NAME**: Database name (alternative to DATABASE_URL)
- **DATABASE_USER**: Database username
- **DATABASE_PASSWORD**: Database password
- **DATABASE_HOST**: Database host
- **DATABASE_PORT**: Database port (default: 5432)

### Django
- **DJANGO_SECRET_KEY**: Django secret key (required)
- **DJANGO_SETTINGS_MODULE**: Django settings module (default: `config.settings`)
- **IS_PRODUCTION**: Set to `True` for production
- **USE_TLS**: Enable HTTPS redirects (default: `True`)

## Setting Environment Variables

### Systemd Service

1. Create environment file:
```bash
sudo nano /etc/systemd/system/smartharvester.service.d/env.conf
```

2. Add all variables (see template above)

3. Ensure service unit includes:
```ini
[Service]
EnvironmentFile=/etc/systemd/system/smartharvester.service.d/env.conf
```

4. Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart smartharvester
```

### Elastic Beanstalk

1. Go to Environment → Configuration → Software
2. Add environment properties
3. Or use `.ebextensions` config file

### Local Development

Create `.env` file in project root:
```bash
cp docs/AWS_ENV_TEMPLATE.md .env
# Edit .env with your values
```

The `python-dotenv` package will load these automatically.

## Verification

After setting environment variables, verify they're loaded:

```bash
# Check systemd service
sudo systemctl show smartharvester --property=Environment

# Check Django settings
python manage.py shell
>>> from django.conf import settings
>>> print(settings.AWS_REGION)
>>> print(settings.DYNAMO_USERS_TABLE)
```

Or use the verification script:
```bash
python scripts/check_env_vars.py
```

## Security Notes

⚠️ **Never commit secrets to version control!**

- Use `.env` files locally (add to `.gitignore`)
- Use systemd environment files on servers
- Use AWS Secrets Manager or Parameter Store for production
- Use IAM instance roles instead of access keys when possible

## Required vs Optional

### Required
- `COGNITO_USER_POOL_ID`
- `COGNITO_DOMAIN`
- `COGNITO_CLIENT_ID`
- `COGNITO_REDIRECT_URI`
- `DYNAMO_USERS_TABLE`
- `DYNAMO_PLANTINGS_TABLE`
- `DJANGO_SECRET_KEY`

### Optional
- `COGNITO_CLIENT_SECRET` (only if app client has secret)
- `DATABASE_URL` (SQLite fallback available)
- `SNS_TOPIC_ARN` (notifications optional)
- `S3_BUCKET` (can use local storage in dev)

