# config/settings.py
# (Your original settings with the single, minimal correction: add 'core' to INSTALLED_APPS)
import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# --- PRODUCTION/DEVELOPMENT SWITCH ---
IS_PRODUCTION = os.environ.get('IS_PRODUCTION', 'False') == 'True'

# --- SECURITY SETTINGS ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-default-development-key')
DEBUG = not IS_PRODUCTION

if IS_PRODUCTION:
    ALLOWED_HOSTS = [os.environ.get('EB_HOSTNAME', '.localhost')]
else:
    ALLOWED_HOSTS = ['3.234.182.130', 'localhost', '127.0.0.1']


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tracker',
    'storages',
    'core',  # <-- ADDED: provides health endpoint and small utilities
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORRECTED: Pointing to the config urls.py
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], # Ensure this is correct if you have a top-level templates dir
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

# CORRECTED: Pointing to the config wsgi.py
WSGI_APPLICATION = 'config.wsgi.application'


# --- DATABASE SETTINGS ---
if IS_PRODUCTION:
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600)
    }
else:
    DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DATABASE_NAME"),
        'USER': os.getenv("DATABASE_USER"),
        'PASSWORD': os.getenv("DATABASE_PASSWORD"),
        'HOST': os.getenv("DATABASE_HOST"),
        'PORT': os.getenv("DATABASE_PORT", "5432"),
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# --- STATIC FILES (CSS, JavaScript, Images) ---
if IS_PRODUCTION:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = 'us-east-1'
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
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
        
# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'