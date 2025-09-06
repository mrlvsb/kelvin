import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request, status

from app.security import HMAC_SIGNATURE_HEADER, validate_signature

TEST_SECRET = "test-secret"
VALID_BODY = b'{"key": "value"}'


@pytest_asyncio.fixture()
async def mock_settings():
    """Fixture to mock get_settings and provide a consistent webhook secret."""
    with patch("app.security.get_settings") as mock_get:
        mock_get.return_value.security.webhook_secret.get_secret_value.return_value = TEST_SECRET
        yield mock_get


def create_mock_request(content: bytes, headers: dict) -> Request:
    """Helper to create a mock FastAPI Request object."""
    request = AsyncMock(spec=Request)
    request.body = AsyncMock(return_value=content)
    request.headers = headers
    return request


def calculate_signature(key: str, body: bytes) -> str:
    """Helper to calculate the expected HMAC signature."""
    digest = hmac.new(key.encode("utf-8"), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_validate_signature_success(mock_settings):
    """Tests that a valid signature passes validation."""
    signature = calculate_signature(TEST_SECRET, VALID_BODY)
    headers = {HMAC_SIGNATURE_HEADER: signature}
    request = create_mock_request(VALID_BODY, headers)

    await validate_signature(request, signature_header=signature)


@pytest.mark.asyncio
async def test_validate_signature_invalid_signature(mock_settings):
    """Tests that an incorrect signature raises a 401 Unauthorized error."""
    wrong_signature = calculate_signature("wrong-secret", VALID_BODY)
    headers = {HMAC_SIGNATURE_HEADER: wrong_signature}
    request = create_mock_request(VALID_BODY, headers)

    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=wrong_signature)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid HMAC signature" in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_signature_tampered_body(mock_settings):
    """Tests that a signature is invalid if the body doesn't match."""
    signature = calculate_signature(TEST_SECRET, b"original body")
    headers = {HMAC_SIGNATURE_HEADER: signature}
    # Request comes in with a different body
    request = create_mock_request(b"tampered body", headers)

    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=signature)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_validate_signature_malformed_header(mock_settings):
    """Tests that a header with an invalid format is rejected."""
    malformed_header = "sha256:invalid-format"
    headers = {HMAC_SIGNATURE_HEADER: malformed_header}
    request = create_mock_request(VALID_BODY, headers)

    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=malformed_header)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid signature header format" in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_signature_missing_header(mock_settings):
    """Tests that missing signature header raises a 401 Unauthorized error."""
    request = create_mock_request(VALID_BODY, headers={})
    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=None)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-Hub-Signature-256 header is missing." in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_signature_empty_header(mock_settings):
    """Tests that an empty signature header raises a 401 Unauthorized error."""
    request = create_mock_request(VALID_BODY, headers={HMAC_SIGNATURE_HEADER: ""})
    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header="")
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-Hub-Signature-256 header is missing." in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_signature_header_wrong_prefix(mock_settings):
    """Tests that a header with wrong prefix is rejected."""
    wrong_prefix_header = "sha1=abcdef" + "0" * 58
    request = create_mock_request(VALID_BODY, headers={HMAC_SIGNATURE_HEADER: wrong_prefix_header})
    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=wrong_prefix_header)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid signature header format" in excinfo.value.detail


@pytest.mark.asyncio
async def test_validate_signature_header_wrong_length(mock_settings):
    """Tests that a header with wrong hash length is rejected."""
    wrong_length_header = "sha256=" + "a" * 10
    request = create_mock_request(VALID_BODY, headers={HMAC_SIGNATURE_HEADER: wrong_length_header})
    with pytest.raises(HTTPException) as excinfo:
        await validate_signature(request, signature_header=wrong_length_header)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid signature header format" in excinfo.value.detail
