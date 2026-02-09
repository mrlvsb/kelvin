from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.deployment import (
    CriticalError,
    DeploymentManager,
    FallbackError,
)
from app.models import ImageInfo


@pytest_asyncio.fixture()
async def mock_docker_client():
    """Provides a mock for the Docker SDK client."""
    with patch("docker.from_env", autospec=True) as mock_from_env:
        mock_from_env.return_value = MagicMock()
        yield mock_from_env.return_value


@pytest_asyncio.fixture()
async def manager_instance(mock_docker_client):
    """Creates a DeploymentManager instance with mocked dependencies."""
    manager = DeploymentManager(
        service_name="app",
        container_name="app_container",
        image={"repository": "ghcr.io/mrlvsb", "image": "kelvin", "tag": "test-sha"},
        commit_sha="a" * 40,
        compose_path=Path("/tmp/test/repo/docker-compose.yml"),
        compose_env_file=Path("/test/repo/.env"),
        healthcheck_url="http://test.local/health",
    )
    manager._watch_container_logs = AsyncMock()  # Disable container logs in test
    manager._run_command = AsyncMock(return_value=True)
    return manager


@pytest.mark.asyncio
async def test_get_current_image_tag_success(manager_instance):
    mock_container = MagicMock()
    mock_container.image.id = "sha256:imgid"
    manager_instance.client.containers.get.return_value = mock_container
    assert manager_instance._get_current_image() == ImageInfo(tag="imgid", id="imgid")


@pytest.mark.asyncio
async def test_obtain_new_image_already_exists(manager_instance):
    mock_image = MagicMock()
    manager_instance.client.images.get.return_value = mock_image
    await manager_instance._obtain_new_image()
    manager_instance.client.images.get.assert_called_once_with(manager_instance.new_image)


@pytest.mark.asyncio
async def test_cleanup_removes_image(manager_instance):
    manager_instance.image_tag = "newtag"
    manager_instance.client.images.remove = MagicMock()
    manager_instance._cleanup("oldid")
    manager_instance.client.images.remove.assert_called_once_with("oldid", force=True)


@pytest.mark.asyncio
async def test_cleanup_skips_if_no_old_image(manager_instance):
    manager_instance.client.images.remove = MagicMock()
    manager_instance._cleanup(None)
    manager_instance.client.images.remove.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_skips_if_same_as_new(manager_instance):
    manager_instance.image_tag = "sameid"
    manager_instance.client.images.remove = MagicMock()
    manager_instance._cleanup("sameid")
    manager_instance.client.images.remove.assert_not_called()


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_health_check_healthy(mock_async_client, manager_instance):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_async_client.return_value.__aenter__.return_value.get = AsyncMock(
        return_value=mock_response
    )
    result = await manager_instance._health_check()
    assert result is True


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_health_check_timeout(mock_sleep, mock_async_client, manager_instance):
    # Fake time that increases every call
    current_time = 0

    def fake_time():
        nonlocal current_time
        current_time += 1
        return current_time

    with patch("time.time", side_effect=fake_time):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_async_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await manager_instance._health_check()

        assert result is False
        assert "HTTP health check timed out." in manager_instance.logs[-1]
        assert mock_sleep.called


@pytest.mark.asyncio
async def test_health_check_docker_healthy(manager_instance):
    manager_instance.healthcheck_url = None
    mock_container = MagicMock()
    mock_container.attrs = {"State": {"Health": {"Status": "healthy"}}}
    manager_instance.client.containers.get.return_value = mock_container

    result = await manager_instance._health_check()
    assert result is True
    assert "Docker health check passed." in manager_instance.logs[-1]


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_health_check_docker_timeout(mock_sleep, manager_instance):
    manager_instance.healthcheck_url = None
    # Fake time that increases every call
    current_time = 0

    def fake_time():
        nonlocal current_time
        current_time += 1
        return current_time

    with patch("time.time", side_effect=fake_time):
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "starting"}}}
        manager_instance.client.containers.get.return_value = mock_container

        result = await manager_instance._health_check()
        assert result is False
        assert "Docker health check timed out." in manager_instance.logs[-1]


@pytest.mark.asyncio
async def test_swap_service_critical_error(manager_instance):
    manager_instance._run_command = AsyncMock(side_effect=[True, False])
    with pytest.raises(CriticalError):
        await manager_instance._swap_service(
            "cur.yml", "cand.yml", image_tag_override="rollbacktag"
        )


@pytest.mark.asyncio
@patch("tempfile.mkdtemp", return_value="/tmp/mock/temp_dir")
@patch("shutil.rmtree")
async def test_run_success(mock_rmtree, mock_mkdtemp, manager_instance):
    """Tests the entire successful deployment workflow."""
    manager_instance._get_current_image = MagicMock(
        return_value=ImageInfo(tag="previous_image_tag", id="previous_image_id")
    )
    manager_instance._obtain_new_image = AsyncMock()
    manager_instance._swap_service = AsyncMock(return_value=True)
    manager_instance._health_check = AsyncMock(return_value=True)
    manager_instance._cleanup = MagicMock()

    logs = await manager_instance.run()

    manager_instance._run_command.assert_any_call(["git", "fetch", "origin"], cwd=ANY)
    manager_instance._run_command.assert_any_call(
        [
            "git",
            "show",
            f"{manager_instance.commit_sha}:{Path(manager_instance.stable_compose_path).name}",
        ],
        cwd=ANY,
        output_file=ANY,
    )

    manager_instance._get_current_image.assert_called_once()
    manager_instance._obtain_new_image.assert_awaited_once()
    manager_instance._swap_service.assert_awaited_once()
    manager_instance._health_check.assert_awaited_once()

    manager_instance._run_command.assert_any_call(
        ["git", "reset", "--hard", manager_instance.commit_sha], cwd=ANY
    )
    manager_instance._cleanup.assert_called_once_with("previous_image_id")

    mock_rmtree.assert_called_once_with("/tmp/mock/temp_dir", ignore_errors=True)
    assert "Deployment successful" in list(logs)[-2]


@pytest.mark.asyncio
async def test_run_rollback_on_health_check_failure(manager_instance):
    """Tests that a rollback is triggered if the health check fails."""
    manager_instance._get_current_image = MagicMock(
        return_value=ImageInfo(tag="previous123", id="previous123_id")
    )
    manager_instance._obtain_new_image = AsyncMock()
    manager_instance._health_check = AsyncMock(return_value=False)

    # Mock _swap_service to inspect its calls
    mock_swap = AsyncMock(return_value=True)
    manager_instance._swap_service = mock_swap

    with pytest.raises(FallbackError):
        await manager_instance.run()

    # Assert that swap was called twice: once for deploy, once for rollback
    assert mock_swap.await_count == 2
    deploy_call, rollback_call = mock_swap.await_args_list

    # Call 1: Standard deployment
    assert "image_tag_override" not in deploy_call.kwargs

    # Call 2: Rollback deployment
    assert rollback_call.kwargs["image_tag_override"] == "previous123"
    assert "Rollback completed" in manager_instance.logs[-2]


@pytest.mark.asyncio
@patch("tempfile.mkdtemp", side_effect=PermissionError("Access denied"))
async def test_run_fails_on_tempdir_creation(mock_mkdtemp, manager_instance):
    """Tests failure when the temporary directory cannot be created."""
    with pytest.raises(CriticalError) as excinfo:
        await manager_instance.run()
    assert "Failed to create temporary directory" in excinfo.value.message
    assert "Access denied" in str(excinfo.value)
