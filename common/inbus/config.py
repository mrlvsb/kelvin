import urllib.parse

INBUS_BASE_URL: str = "https://inbus.vsb.cz/service/"
INBUS_SERVICE_EDISON_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, "edison/v1/")
INBUS_SERVICE_IDM_URL: str = urllib.parse.urljoin(INBUS_BASE_URL, "idm/v1/")

INBUS_TOKEN_URL: str = "https://inbus.vsb.cz/oauth/token"
