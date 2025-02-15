from .base import *

DEBUG = True
# ALLOWED_HOSTS = ['127.0.0.1']
ALLOWED_HOSTS = ["*"]


INSTALLED_APPS += ["debug_toolbar"]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

# DEBUG TOOLBAR SETTINGS

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.logging.LoggingPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
]


def show_toolbar(request):
    return True


DEBUG_TOOLBAR_CONFIG = {
    "INTERCEPT_REDIRECTS": False,
    "SHOW_TOOLBAR_CALLBACK": show_toolbar,
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DB_PATH", os.path.join(BASE_DIR, "db.sqlite3")),
    }
}

STRIPE_PUBLIC_KEY = config("STRIPE_TEST_PUBLIC_KEY")
STRIPE_SECRET_KEY = config("STRIPE_TEST_SECRET_KEY")

SHOPCANAL_API_BASE_URL = os.environ.get(
    "SHOPCANAL_API_BASE_URL", "http://localhost:8080"
)
CANAL_APP_ID = os.environ.get("CANAL_APP_ID", "c13012fd-fd99-458b-a89e-4bf1e4cbae03")
CANAL_ACCESS_TOKEN = os.environ.get(
    "CANAL_ACCESS_TOKEN", "48c0e282456c4d029978259ab765e1e8"
)
