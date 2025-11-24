# SmartHarvester Architecture

## Complete AWS Architecture Flow

This document describes the complete architecture flow of the SmartHarvester application, showing how all AWS services integrate together.

## Architecture Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Web Application (Django)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Django Admin (User Management)                     │   │
│  └──────────────────────────────────────────────────────┘   │
└────┬────────────────────────────────────────────────────────┘
     │
     ├─────────────────────────────────────────────────────────┐
     │                                                         │
     ▼                                                         ▼
┌──────────────────┐                                  ┌──────────────────┐
│  AWS Cognito     │                                  │  Django Views    │
│  (Authentication)│                                  │  (Planting CRUD) │
└────┬─────────────┘                                  └────┬─────────────┘
     │                                                      │
     │ 1. User Sign-up/Login                               │
     ▼                                                      │
┌──────────────────┐                                      │
│  Lambda Triggers  │                                      │
│  ┌──────────────┐ │                                      │
│  │ Pre Sign-up  │ │                                      │
│  │ (Auto-confirm)│ │                                      │
│  └──────────────┘ │                                      │
│  ┌──────────────┐ │                                      │
│  │Post Confirmation│                                      │
│  │ (Save to DynamoDB)│                                    │
│  └──────────────┘ │                                      │
└────┬─────────────┘                                      │
     │                                                      │
     │ 2. Put new user to DynamoDB users table             │
     ▼                                                      │
┌──────────────────┐                                      │
│  DynamoDB        │                                      │
│  ┌──────────────┐ │                                      │
│  │ users table  │ │                                      │
│  └──────────────┘ │                                      │
└──────────────────┘                                      │
     │                                                      │
     │                                                      │
     │ 3. User adds plants                                  │
     │                                                      │
     │                                                      ▼
     │                                            ┌──────────────────┐
     │                                            │ PyPI Library     │
     │                                            │ (dynamodb_helper)│
     │                                            └────┬─────────────┘
     │                                                 │
     │                                                 │ 4. Push to DynamoDB
     │                                                 │    plantings table
     │                                                 ▼
     │                                        ┌──────────────────┐
     │                                        │  DynamoDB        │
     │                                        │  ┌──────────────┐│
     │                                        │  │plantings table││
     │                                        │  └──────────────┘│
     │                                        └──────────────────┘
     │
     │ 5. User uploads images
     │
     ▼
┌──────────────────┐
│  Amazon S3       │
│  (Image Storage)  │
└──────────────────┘
     │
     │ 6. Email notifications
     │
     ▼
┌──────────────────┐
│  Amazon SNS      │
│  (Notifications) │
└──────────────────┘
     │
     │ 7. Backend database
     │
     ▼
┌──────────────────┐
│  Amazon RDS      │
│  (PostgreSQL)    │
│  (Django Admin)  │
└──────────────────┘
```

## Detailed Flow Breakdown

### 1. User Authentication Flow

**Path:** `User → Webapp → Cognito → Lambda → DynamoDB`

1. **User accesses webapp** (`https://3.235.196.246.nip.io`)
2. **Clicks login** → Redirected to Cognito Hosted UI
3. **Cognito authentication:**
   - User signs up or logs in
   - Cognito validates credentials
4. **Lambda Triggers:**
   - **Pre Sign-up Lambda** (`lambda/cognito_auto_confirm.py`):
     - Auto-confirms user
     - Auto-verifies email/phone
   - **Post Confirmation Lambda** (`lambda/post_confirmation_lambda.py`):
     - Extracts user attributes from Cognito event
     - Saves user to DynamoDB `users` table
5. **User data stored in DynamoDB:**
   - `username` (PK)
   - `user_id` (Cognito sub)
   - `email`, `name`, etc.

**Files:**
- `tracker/views.py` - `cognito_login()`, `cognito_callback()`
- `lambda/cognito_auto_confirm.py` - Pre sign-up trigger
- `lambda/post_confirmation_lambda.py` - Post confirmation trigger
- `tracker/dynamodb_helper.py` - `save_user_to_dynamodb()`

### 2. User Adds Plants Flow

**Path:** `User → Webapp → PyPI Library → DynamoDB`

1. **User adds planting:**
   - Fills form (crop name, date, notes, image)
   - Submits via `save_planting()` view
2. **Image upload to S3:**
   - `tracker/s3_helper.py` - `upload_planting_image()`
   - Uploads to: `s3://terratrack-media/media/planting_images/{user_id}/{filename}`
   - Returns public URL: `https://terratrack-media.s3.us-east-1.amazonaws.com/...`
3. **Save to DynamoDB:**
   - Uses PyPI library: `tracker/dynamodb_helper.py`
   - Function: `save_planting_to_dynamodb(planting_dict)`
   - Saves to `plantings` table with:
     - `planting_id` (PK)
     - `user_id` (Cognito sub)
     - `username` (for querying)
     - `crop_name`, `planting_date`, `batch_id`, `notes`
     - `image_url` (S3 URL)
     - `plan` (calculated care plan)

**Files:**
- `tracker/views.py` - `save_planting()`
- `tracker/s3_helper.py` - `upload_planting_image()`
- `tracker/dynamodb_helper.py` - `save_planting_to_dynamodb()`

### 3. Image Upload Flow

**Path:** `User → Webapp → S3`

1. **User selects image** in planting form
2. **Django receives file** via `request.FILES['image']`
3. **Upload to S3:**
   - Bucket: `terratrack-media` (configurable via `S3_BUCKET` env var)
   - Key: `media/planting_images/{user_id}/{filename}`
   - Content-Type: Preserved from upload
4. **Public URL returned:**
   - Format: `https://{bucket}.s3.{region}.amazonaws.com/{key}`
   - Stored in DynamoDB `plantings` table as `image_url`

**Files:**
- `tracker/s3_helper.py` - `upload_planting_image()`
- `tracker/views.py` - `save_planting()` (calls S3 upload)

### 4. Email Notifications Flow

**Path:** `Django Management Command → SNS → Email`

1. **Scheduled task** (cron or EventBridge):
   - Runs: `python manage.py send_harvest_reminders --days 3`
2. **Management command:**
   - `tracker/management/commands/send_harvest_reminders.py`
   - Loads all users from DynamoDB
   - For each user, loads their plantings
   - Checks for upcoming harvest tasks
3. **SNS notification:**
   - `tracker/sns_helper.py` - `send_harvest_reminder()`
   - Subscribes email to SNS topic (if not already)
   - Publishes message to SNS topic
4. **Email delivery:**
   - SNS sends email to user
   - User receives harvest reminder

**Files:**
- `tracker/management/commands/send_harvest_reminders.py`
- `tracker/sns_helper.py` - `send_harvest_reminder()`, `subscribe_email_to_topic()`
- `lambda/notification_lambda.py` - Alternative Lambda-based notifications

**Configuration:**
- `SNS_TOPIC_ARN` - SNS topic ARN for notifications

### 5. RDS Backend (Django Admin)

**Path:** `Django Admin → RDS PostgreSQL`

1. **Django Admin access:**
   - URL: `/admin/`
   - Uses Django's built-in admin interface
2. **User management:**
   - Admin can manage Django User model
   - Stored in RDS PostgreSQL database
3. **Database configuration:**
   - Production: Uses `DATABASE_URL` (RDS endpoint)
   - Development: Uses `DATABASE_NAME` or SQLite fallback
4. **Django signals:**
   - `tracker/signals.py` - Syncs Django users to DynamoDB
   - On User save → Updates DynamoDB `users` table

**Files:**
- `config/settings.py` - Database configuration
- `tracker/signals.py` - Django signals for user sync
- `infrastructure.yml` - CloudFormation template for RDS

**Infrastructure:**
- RDS PostgreSQL instance (via CloudFormation)
- Security groups for Elastic Beanstalk access

### 6. Deployment Pipeline

**Path:** `Webapp Changes → Cloud Pipeline → EBS Deploy → New Changes`

1. **Code changes:**
   - Developer pushes to repository
   - Code includes Django app, Lambda functions, infrastructure
2. **CI/CD Pipeline:**
   - **CodeBuild** (via `buildspec.yml`):
     - Installs Python 3.10
     - Installs dependencies (`requirements.txt`)
     - Runs tests
     - Creates deployment artifact
3. **Elastic Beanstalk deployment:**
   - Deploys Django application
   - Configures environment variables
   - Sets up Gunicorn/WSGI server
   - Connects to RDS database
4. **Lambda deployment:**
   - Deploy Lambda functions separately:
     - `cognito_auto_confirm.py` → Pre sign-up trigger
     - `post_confirmation_lambda.py` → Post confirmation trigger
     - `notification_lambda.py` → Scheduled notifications
5. **Infrastructure updates:**
   - CloudFormation (`infrastructure.yml`) for RDS
   - Manual setup for Cognito, DynamoDB, S3, SNS

**Files:**
- `buildspec.yml` - CodeBuild configuration
- `infrastructure.yml` - CloudFormation template
- `requirements.txt` - Python dependencies
- `config/settings.py` - Environment-based configuration

## AWS Services Used

### 1. **Amazon Cognito**
- **Purpose:** User authentication and authorization
- **Components:**
  - User Pool: `us-east-1_HGEM2vRNI`
  - Domain: `smartcrop-rocky-app.auth.us-east-1.amazoncognito.com`
  - App Client: `4l8j19f73h5hqmlldgc6jigk3k`
- **Integration:**
  - Hosted UI for login/signup
  - Lambda triggers for user management
  - JWT tokens for session management

### 2. **AWS Lambda**
- **Functions:**
  - `cognito-auto-confirm` - Pre sign-up trigger (auto-confirm users)
  - `post-confirmation` - Post confirmation trigger (save to DynamoDB)
  - `notification-lambda` - Scheduled notifications (optional)
- **Triggers:**
  - Cognito User Pool triggers
  - EventBridge (for scheduled tasks)

### 3. **Amazon DynamoDB**
- **Tables:**
  - `users` - User data (PK: `username`)
  - `plantings` - Planting data (PK: `planting_id`, GSI: `user_id-index`)
- **Operations:**
  - `PutItem` - Save users/plantings
  - `Query` - Load user plantings via GSI
  - `Scan` - Fallback query method
  - `UpdateItem` - Update user/planting data
  - `DeleteItem` - Delete plantings

### 4. **Amazon S3**
- **Bucket:** `terratrack-media` (configurable)
- **Purpose:** Store planting images
- **Structure:**
  - `media/planting_images/{user_id}/{filename}`
- **Access:** Public URLs for image display

### 5. **Amazon SNS**
- **Purpose:** Email notifications for harvest reminders
- **Topic:** `harvest-notifications` (configurable via `SNS_TOPIC_ARN`)
- **Operations:**
  - Subscribe email addresses
  - Publish notification messages

### 6. **Amazon RDS**
- **Engine:** PostgreSQL 15
- **Purpose:** Django backend database
- **Usage:**
  - Django admin user management
  - Django sessions (optional)
  - Django migrations
- **Infrastructure:** CloudFormation template (`infrastructure.yml`)

### 7. **AWS Elastic Beanstalk**
- **Purpose:** Application deployment and hosting
- **Platform:** Python 3.10
- **Configuration:**
  - Environment variables from systemd or EB config
  - Gunicorn WSGI server
  - Nginx reverse proxy (if configured)

### 8. **AWS CodeBuild**
- **Purpose:** CI/CD pipeline
- **Configuration:** `buildspec.yml`
- **Steps:**
  - Install Python 3.10
  - Install dependencies
  - Run tests
  - Create deployment artifact

## Data Flow Summary

### User Registration
```
User → Webapp → Cognito Sign-up
  → Lambda (Pre Sign-up) → Auto-confirm
  → Cognito User Created
  → Lambda (Post Confirmation) → DynamoDB users table
```

### User Login
```
User → Webapp → Cognito Login
  → Cognito Hosted UI
  → Authorization Code
  → Webapp exchanges code for tokens
  → Tokens saved to session
  → User data loaded from DynamoDB
```

### Add Planting
```
User → Webapp Form
  → Image upload → S3
  → Planting data → PyPI library (dynamodb_helper)
  → DynamoDB plantings table
  → Session cache (for immediate UI)
```

### View Plantings
```
User → Webapp Dashboard
  → Extract user_id from session/middleware
  → Query DynamoDB plantings table (GSI: user_id-index)
  → Load images from S3 URLs
  → Display to user
```

### Notifications
```
Scheduled Task → Management Command
  → Load users from DynamoDB
  → Load plantings for each user
  → Check for upcoming tasks
  → SNS publish → Email delivery
```

## Environment Variables

### Required for All Environments
```bash
# Cognito
COGNITO_USER_POOL_ID=us-east-1_HGEM2vRNI
COGNITO_REGION=us-east-1
COGNITO_DOMAIN=smartcrop-rocky-app.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=4l8j19f73h5hqmlldgc6jigk3k
COGNITO_REDIRECT_URI=https://3.235.196.246.nip.io/auth/callback/

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# DynamoDB
DYNAMO_USERS_TABLE=users
DYNAMO_PLANTINGS_TABLE=plantings
DYNAMO_USERS_PK=username

# S3
S3_BUCKET=terratrack-media

# SNS (optional)
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications

# Django
DJANGO_SECRET_KEY=...
IS_PRODUCTION=True/False

# RDS (production)
DATABASE_URL=postgresql://user:password@rds-endpoint:5432/dbname
```

## IAM Permissions Required

### EC2/Elastic Beanstalk Instance Role
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

### Lambda Execution Roles
- **Cognito triggers:** `AWSLambdaBasicExecutionRole` + DynamoDB write permissions
- **Notification Lambda:** DynamoDB read + SNS publish permissions

## Deployment Checklist

### Initial Setup
- [ ] Create Cognito User Pool
- [ ] Configure Cognito Domain
- [ ] Create DynamoDB tables (`users`, `plantings`)
- [ ] Create S3 bucket for images
- [ ] Create SNS topic for notifications
- [ ] Deploy Lambda functions
- [ ] Attach Lambda triggers to Cognito
- [ ] Create RDS instance (via CloudFormation)
- [ ] Configure IAM roles and permissions

### Application Deployment
- [ ] Set environment variables in Elastic Beanstalk
- [ ] Deploy Django application to EBS
- [ ] Configure CodeBuild pipeline
- [ ] Test authentication flow
- [ ] Test planting creation
- [ ] Test image uploads
- [ ] Test notifications

### Ongoing Maintenance
- [ ] Monitor CloudWatch logs
- [ ] Monitor DynamoDB metrics
- [ ] Monitor S3 storage usage
- [ ] Review IAM permissions
- [ ] Update Lambda functions as needed
- [ ] Deploy code changes via pipeline

## Summary

This architecture uses AWS services for:
- **Authentication:** Cognito + Lambda
- **Data Storage:** DynamoDB (users, plantings) + RDS (Django admin)
- **File Storage:** S3 (images)
- **Notifications:** SNS (email)
- **Deployment:** Elastic Beanstalk + CodeBuild
- **Backend:** RDS PostgreSQL (Django admin)

All components are integrated and work together to provide a scalable, serverless-friendly architecture for the SmartHarvester application.

