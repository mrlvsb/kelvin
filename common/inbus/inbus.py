import urllib.parse

from typing import Dict, Optional

from . import dto, utils

INBUS_BASE_URL: str = 'https://inbus.vsb.cz/service/'
INBUS_SERVICE_EDISON_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, 'edison/v1/')
INBUS_SERVICE_IDM_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, 'idm/v1/')


# Actual INBUS API calls

def person_by_login(login: str) -> Optional[dto.PersonSimple]:
    url = urllib.parse.urljoin(INBUS_SERVICE_IDM_URL, f'person/login/{login}')

    person_resp = utils.inbus_request(url, {})
    if not person_resp:
        return None
    person_json = person_resp.json()

    # INBUS may return response that has missing fields
    if 'login' not in person_json:
        return None

    person_simple = dto.PersonSimple(login=person_json["login"].upper(), first_name=person_json.get('firstName', ''), second_name=person_json.get('secondName', ''),
                                full_name=person_json.get('fullName', ''), email=person_json.get('email', ''))

    return person_simple


# Kelvin's interface

def search_user(login: str) -> Optional[dto.PersonSimple]:
    person_inbus = person_by_login(login)

    return person_inbus