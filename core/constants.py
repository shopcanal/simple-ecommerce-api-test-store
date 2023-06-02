from django.conf import settings


SHOPCANAL_DEFAULT_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "X-CANAL-APP-ID": settings.CANAL_APP_ID,
    "X-CANAL-APP-TOKEN": settings.CANAL_ACCESS_TOKEN,
}
