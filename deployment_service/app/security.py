import hashlib
import hmac
import re

from fastapi import HTTPException, Request, status, Security
from fastapi.security import APIKeyHeader
from app.config import get_settings

HMAC_SIGNATURE_PATTERN = re.compile(r"^sha256=([0-9a-fA-F]{64})$")
HMAC_SIGNATURE_HEADER = "X-Hub-Signature-256"

api_key_header = APIKeyHeader(name=HMAC_SIGNATURE_HEADER, scheme_name="HMACSignature")


async def validate_signature(
    request: Request, signature_header: str = Security(api_key_header)
) -> None:
    """
    Validates the HMAC signature of the incoming webhook request.

    Raises:
        HTTPException: If the signature header is missing.
        HTTPException: If the signature header format is invalid.
        HTTPException: If the signature is invalid.
    """

    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Hub-Signature-256 header is missing.",
        )

    match = HMAC_SIGNATURE_PATTERN.fullmatch(signature_header)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature header format."
        )

    signature = match.group(1)

    body = await request.body()
    expected_signature = hmac.new(
        get_settings().security.webhook_secret.get_secret_value().encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature."
        )
