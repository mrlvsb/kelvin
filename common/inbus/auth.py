from typing import Dict

from django.conf import settings
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from . import config


def authenticate(client_id=settings.INBUS_CLIENT_ID, client_secret=settings.INBUS_CLIENT_SECRET) -> Dict:
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url=config.INBUS_TOKEN_URL, client_id=client_id, client_secret=client_secret)

    return token

