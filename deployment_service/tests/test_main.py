import json
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient

from app import config
from app.deployment import CriticalError, DeploymentError, FallbackError
from tests.test_security import calculate_signature

# Mock settings before importing the app
mock_settings = AsyncMock()
mock_settings.security.allowed_hosts = ["testserver", "nginx"]
mock_settings.security.backend_cors_origins = ["http://localhost"]
mock_settings.docker.compose_file_path = "/tmp/docker-compose.yml"
config.get_settings = lambda: mock_settings

from app.main import app  # noqa: E402

client = TestClient(app)

TEST_WEBHOOK_SECRET = "yoursecretvalue"

VALID_PAYLOAD = json.dumps(
    {
        "service_name": "app",
        "container_name": "project_app",
        "image": "ghcr.io/mrlvsb/kelvin:latest",
        "commit_sha": "ffac537e6cbbf934b08745a378932722df287a53",
    }
)


@pytest_asyncio.fixture(name="default_user_headers", scope="function")
async def fixture_default_user_headers() -> dict[str, str]:
    return {
        "X-Hub-Signature-256": calculate_signature(
            TEST_WEBHOOK_SECRET, VALID_PAYLOAD.encode("utf-8")
        )
    }


@pytest_asyncio.fixture()
async def mock_deployment_manager():
    """Mocks the DeploymentManager class."""
    with patch("app.main.DeploymentManager", autospec=True) as mock_dm:
        mock_instance = mock_dm.return_value
        mock_instance.run = AsyncMock(return_value=["Successful log"])
        yield mock_instance


def test_get_health_endpoint():
    """Tests the /health endpoint for a successful response."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "OK"}


def test_deploy_success(mock_deployment_manager, default_user_headers):
    """Tests the successful / endpoint."""
    response = client.post("/", content=VALID_PAYLOAD, headers=default_user_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"logs": ["Successful log"], "error": None}

    mock_deployment_manager.run.assert_awaited_once()


def test_deploy_fallback_error(mock_deployment_manager, default_user_headers):
    """Tests the response when a recoverable FallbackError occurs."""
    mock_deployment_manager.run.side_effect = FallbackError(
        "Health check failed", logs=["Health check timed out."]
    )

    response = client.post("/", content=VALID_PAYLOAD, headers=default_user_headers)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {
        "logs": ["Health check timed out."],
        "error": "Health check failed",
    }


def test_deploy_critical_error(mock_deployment_manager, default_user_headers):
    """Tests the response when a CriticalError occurs."""
    mock_deployment_manager.run.side_effect = CriticalError(
        "Git failed",
        logs=["Git command failed."],
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

    response = client.post("/", content=VALID_PAYLOAD, headers=default_user_headers)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"logs": ["Git command failed."], "error": "Git failed"}


def test_deploy_image_pull_error(mock_deployment_manager, default_user_headers):
    """Tests the response when an image pull fails (400 Bad Request)."""
    mock_deployment_manager.run.side_effect = DeploymentError(
        "Image not found", logs=["Failed to pull image."], status_code=status.HTTP_400_BAD_REQUEST
    )

    response = client.post("/", content=VALID_PAYLOAD, headers=default_user_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"logs": ["Failed to pull image."], "error": "Image not found"}


def test_cors_headers_present():
    """Test that CORS headers are present in responses."""
    response = client.options("/", headers={"Origin": "http://localhost"})
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost"


def test_trusted_host_middleware_blocks_untrusted_host():
    """Test that requests from untrusted hosts are blocked."""
    response = client.get("/health", headers={"host": "malicious.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
