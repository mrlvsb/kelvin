import json
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient

from app import config
from tests.test_security import calculate_signature

# Mock settings before importing the app
mock_settings = AsyncMock()
mock_settings.security.allowed_hosts = ["testserver", "nginx"]
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
