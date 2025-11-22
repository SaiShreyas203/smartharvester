import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

IS_PRODUCTION = os.environ.get('IS_PRODUCTION', 'False') == 'True'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-default-development-key')
DEBUG = not IS_PRODUCTION

load_dotenv()

COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN")
COGNITO_REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")
COGNITO_REGION = os.getenv("COGNITO_REGION")

if IS_PRODUCTION:
    allowed_hosts_list = [os.environ.get('EB_HOSTNAME', '.localhost')]
    if '3.235.196.246.nip.io' not in allowed_hosts_list:
        allowed_hosts_list.append('3.235.196.246.nip.io')
    ALLOWED_HOSTS = allowed_hosts_list
else:
    ALLOWED_HOSTS = ['3.235.196.246.nip.io', '3.235.196.246', 'localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tracker',
    'storages',
    'core',  # provides health endpoint and small utilities
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tracker.middleware.CognitoTokenMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- DATABASE SETTINGS ---
if IS_PRODUCTION:
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600)
    }
else:
    # Ensure HOST is set to avoid Unix socket connection attempts
    db_host = os.getenv("DATABASE_HOST")
    if not db_host or db_host.strip() == '':
        db_host = 'localhost'
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv("DATABASE_NAME"),
            'USER': os.getenv("DATABASE_USER"),
            'PASSWORD': os.getenv("DATABASE_PASSWORD"),
            'HOST': db_host,
            'PORT': os.getenv("DATABASE_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# -------- AWS S3 KEYS ALWAYS DEFINED! --------
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
# region name can be set via env or default to us-east-1
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

# --- STATIC FILES (CSS, JavaScript, Images) ---
if IS_PRODUCTION:
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    STATIC_LOCATION = 'static'
    MEDIA_LOCATION = 'media'

    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_LOCATION}/'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/'

    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    from storages.backends.s3boto3 import S3Boto3Storage
    class MediaStorage(S3Boto3Storage):
        location = MEDIA_LOCATION
        file_overwrite = False
    DEFAULT_FILE_STORAGE = 'config.settings.MediaStorage'
else:
    STATIC_URL = 'static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
        
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/auth/login/'