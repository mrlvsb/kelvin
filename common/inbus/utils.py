import requests

from typing import Dict

from django.core.cache import caches

from . import auth


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
        token = auth.authenticate()
        set_token_to_cache(token)
    return token


def request_new_token() -> Dict:
    token = auth.authenticate()
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


def inbus_request(url, params: Dict = None) -> requests.Response | None:
    if params is None:
        params = {}
    token = inbus_token()
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Accept": "application/json",
        "Accept-Language": "cz"
        }

    try:
        response = requests.get(url, headers=headers, params=params)
        if not is_response_ok_or_new_token_(response):
            response = requests.get(url, headers=headers, params=params)

            # if we still don't get right response, fail with None
            if response.status_code != requests.codes.OK:
                return None

        return response
    except requests.exceptions.ConnectionError:
        return None
