import os
from pathlib import Path
from decouple import config
from datetime import timedelta
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-temporary-key-for-development')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# Get Render URL from environment
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# Allowed hosts for both local and production
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.onrender.com',
    'business.onrender.com',
]

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'django_celery_beat',
    
    # Custom apps
    'accounts',
    'suppliers',
    'products',
    'orders',
    'payments',
    'dashboard',
    'team',
    'analytics',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.RoleBasedAccessMiddleware',
    'accounts.middleware.LoginLoggingMiddleware',
]

ROOT_URLCONF = 'heros_technology.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'heros_technology.wsgi.application'

# DATABASE CONFIGURATION
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }
    DATABASES['default']['CONN_MAX_AGE'] = 600
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True
    if 'sslmode' not in DATABASE_URL:
        DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='heros_db'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='password'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ========== EMAIL CONFIGURATION FOR BREVO ==========
# Priority: 1. Render ENV variables, 2. Local .env, 3. Console backend fallback

# Get email configuration from environment
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp-relay.brevo.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Check if we're on Render
on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)

# Use a proper "From" email address - IMPORTANT for Gmail deliverability
# Option 1: Use verified Gmail (if you've verified it in Brevo)
# Option 2: Use Brevo's default but with proper name
if EMAIL_HOST_USER:
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
else:
    DEFAULT_FROM_EMAIL = 'noreply@heros-technology.com'

# For Gmail deliverability, set a proper sender name
DEFAULT_FROM_EMAIL_NAME = config('DEFAULT_FROM_EMAIL_NAME', default='HerosTechnology')

# If using Gmail as sender, use this format: "HerosTechnology <blacksiteoff@gmail.com>"
if '@gmail.com' in DEFAULT_FROM_EMAIL:
    DEFAULT_FROM_EMAIL = f"{DEFAULT_FROM_EMAIL_NAME} <{DEFAULT_FROM_EMAIL}>"

# Try Brevo API first (better deliverability than SMTP on Render)
USE_BREVO_API = config('USE_BREVO_API', default=True, cast=bool)

if USE_BREVO_API and not DEBUG:
    try:
        # Configure for Brevo API (better than SMTP on Render free tier)
        INSTALLED_APPS.insert(0, 'anymail')
        EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
        ANYMAIL = {
            "BREVO_API_KEY": config('BREVO_API_KEY', default=''),
        }
        print("✅ Using Brevo API for email delivery")
    except Exception as e:
        print(f"⚠️ Brevo API not configured: {e}, falling back to SMTP")

# Fallback to console backend on Render if email not configured
if on_render and not EMAIL_HOST_USER and not config('BREVO_API_KEY', default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    print("⚠️ Using console email backend on Render (emails will appear in logs)")

# For local development, use console backend if no SMTP configured
if DEBUG and not EMAIL_HOST_USER and not config('BREVO_API_KEY', default=''):
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    print("📧 Using console email backend for development")

# OTP Settings
OTP_EXPIRY_MINUTES = config('OTP_EXPIRY_MINUTES', default=5, cast=int)

# Payment Settings
PAYMENT_MODE = config('PAYMENT_MODE', default='simulated')

# Cache Configuration
if os.environ.get('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.environ.get('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Login URL
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGOUT_REDIRECT_URL = 'home'

# Session Settings
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True

# VAT Rate
VAT_RATE = 18

# Commission Rate
COMMISSION_RATE = 7

# Site URL
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    SITE_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"
else:
    SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Payment settings
PAYMENT_SANDBOX_MODE = config('PAYMENT_SANDBOX_MODE', default=True, cast=bool)

# MTN Mobile Money API
MTN_API_USER = os.environ.get('MTN_API_USER', '')
MTN_API_KEY = os.environ.get('MTN_API_KEY', '')
MTN_SUBSCRIPTION_KEY = os.environ.get('MTN_SUBSCRIPTION_KEY', '')

# Airtel Money API
AIRTEL_CLIENT_ID = os.environ.get('AIRTEL_CLIENT_ID', '')
AIRTEL_CLIENT_SECRET = os.environ.get('AIRTEL_CLIENT_SECRET', '')
AIRTEL_API_KEY = os.environ.get('AIRTEL_API_KEY', '')

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True