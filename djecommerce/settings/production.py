from .base import *

# DEBUG = config('DEBUG', cast=bool)
# ALLOWED_HOSTS = ['ip-address', 'www.your-website.com']
DEBUG = True
ALLOWED_HOSTS = ["*"]


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": "",
    }
}

STRIPE_PUBLIC_KEY = "pk_test_51MyNecBPRjE4EZIhfqc07HDwRVKCabyigjsSjHfCTpoaanifaeK4N9Nmq1Gk6WaJUc3b9CLBklSdvOVX3N2wDj5h00TcW1PWbO"
STRIPE_SECRET_KEY = "sk_test_51MyNecBPRjE4EZIhe1Eujz6Vt8TUlIa8BFRqUqqXBPl81vLIsnS7ZG4B06I2B5q881nTrS2rtyIWlWcxFbHDB1Gw00VkzxUgWJ"


SHOPCANAL_API_BASE_URL = "https://api.shopcanal.com/platform"
CANAL_APP_ID = "c13012fd-fd99-458b-a89e-4bf1e4cbae03"
CANAL_ACCESS_TOKEN = "48c0e282456c4d029978259ab765e1e8"
