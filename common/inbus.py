import requests
import urllib.parse

from dataclasses import dataclass
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
from typing import Dict, Optional

from django.conf import settings
from django.core.cache import caches

INBUS_BASE_URL: str = 'https://inbus.vsb.cz/service/'
INBUS_SERVICE_EDISON_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, 'edison/v1/')
INBUS_SERVICE_IDM_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, 'idm/v1/')


@dataclass
class PersonSimple:
    """
    Info about person provided by DTO from INBUS. Not all attributes are present since we don't need them.
    Attribute names are in PEP-8 convention.
    """
    login: str
    full_name: str
    first_name: str
    second_name: str
    email: str


def authenticate(client_id=settings.INBUS_CLIENT_ID, client_secret=settings.INBUS_CLIENT_SECRET) -> Dict:
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url='https://inbus.vsb.cz/oauth/token', client_id=client_id, client_secret=client_secret)

    return token


def set_token_to_cache(token: Dict) -> None:
    """
    Sets INBUS token to cache.
    We set its timeout to one hour less than epecified by API provider.
    """
    cache = caches["default"]
    timeout = token["expires_in"] - 3600 if token["expires_in"] > 3600 else token["expires_in"]
    cache.set("inbus_token", token, timeout=timeout) # one hour less than provided


def inbus_token() -> Dict:
    """
    Returns current INBUS token.
    Either it's one that is cached or new one returned by authentication to INBUS.
    """
    cache = caches["default"]
    token = cache.get("inbus_token")

    if not token:
        token = authenticate()
        set_token_to_cache(token)
    return token


def request_new_token() -> Dict:
    token = authenticate()
    return token


def is_response_ok_or_new_token_(response: requests.Response) -> bool:
    if response.status_code == requests.codes.OK:
        return True
    elif response.status_code == requests.codes.UNAUTHORIZED:
        token = request_new_token()
        set_token_to_cache(token)
        return False
    else:
        return False


def inbus_request(url, params={}):
    token = inbus_token()
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Accept" : "application/json",
        "Accept-Language" : "cz"
        }

    response = requests.get(url, headers=headers, params=params)
    if not is_response_ok_or_new_token_(response):
        response = requests.get(url, headers=headers, params=params)
        
        # if we still don't get right response, fail with None
        if response.status_code != 200:
            return None

    return response


# Actual INBUS API calls

def person_by_login(login: str) -> Optional[PersonSimple]:
    url = urllib.parse.urljoin(INBUS_SERVICE_IDM_URL, f'person/login/{login}')

    person_resp = inbus_request(url, {})
    if not person_resp:
        return None
    person_json = person_resp.json()

    person_simple = PersonSimple(login=person_json["login"].upper(), first_name=person_json["firstName"], second_name=person_json["secondName"],
                                full_name=person_json["fullName"], email=person_json["email"])
    return person_simple


# Kelvin's interface

def search_user(login: str) -> Optional[PersonSimple]:
    person_inbus = person_by_login(login)

    return person_inbus