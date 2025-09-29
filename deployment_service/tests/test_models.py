import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.models import DeploymentRequest


def test_parse_image_valid():
    req = DeploymentRequest(
        service_name="app",
        container_name="project_app",
        image="ghcr.io/mrlvsb/kelvin:latest",
        commit_sha="ffac537e6cbbf934b08745a378932722df287a53",
        healthcheck_url="https://nginx/health",
    )
    assert req.image["repository"] == "ghcr.io"
    assert req.image["image"] == "mrlvsb/kelvin"
    assert req.image["tag"] == "latest"


def test_parse_image_invalid():
    with pytest.raises(ValidationError) as exc:
        DeploymentRequest(
            service_name="app",
            container_name="project_app",
            image="invalidimageformat",
            commit_sha="ffac537e6cbbf934b08745a378932722df287a53",
            healthcheck_url="https://nginx/health",
        )
    assert "Invalid image format" in str(exc.value)


def test_healthcheck_url_allowed_host(monkeypatch):
    req = DeploymentRequest(
        service_name="app",
        container_name="project_app",
        image="ghcr.io/mrlvsb/kelvin:latest",
        commit_sha="ffac537e6cbbf934b08745a378932722df287a53",
        healthcheck_url="https://nginx/health",
    )
    assert req.healthcheck_url.host in get_settings().security.allowed_hosts


def test_healthcheck_url_disallowed_host():
    with pytest.raises(ValidationError) as exc:
        DeploymentRequest(
            service_name="app",
            container_name="project_app",
            image="ghcr.io/mrlvsb/kelvin:latest",
            commit_sha="ffac537e6cbbf934b08745a378932722df287a53",
            healthcheck_url="https://notallowed.com/health",
        )
    assert "healthcheck_url host must be one of" in str(exc.value)
