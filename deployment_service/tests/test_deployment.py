from collections import deque
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from docker.errors import APIError, ImageNotFound, NotFound

from app.deployment import (
    CriticalError,
    DeploymentManager,
    FallbackError,
)


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
    )
    manager._run_command = AsyncMock(return_value=True)
    return manager


@pytest.mark.asyncio
async def test_get_current_image_id_success(manager_instance):
    mock_container = MagicMock()
    mock_container.image.id = "sha256:imgid"
    manager_instance.client.containers.get.return_value = mock_container
    assert manager_instance._get_current_image_id() == "imgid"


@pytest.mark.asyncio
async def test_get_current_image_id_no_image(manager_instance):
    mock_container = MagicMock()
    mock_container.image = None
    manager_instance.client.containers.get.return_value = mock_container
    assert manager_instance._get_current_image_id() is None


@pytest.mark.asyncio
async def test_get_current_image_id_not_found(manager_instance):
    manager_instance.client.containers.get.side_effect = NotFound("Container not found")
    assert manager_instance._get_current_image_id() is None


@pytest.mark.asyncio
async def test_pull_new_image_already_exists(manager_instance):
    mock_image = MagicMock()
    manager_instance.client.images.get.return_value = mock_image
    manager_instance._pull_new_image()
    manager_instance.client.images.get.assert_called_once_with(manager_instance.new_image)


@pytest.mark.asyncio
async def test_pull_new_image_pulls_when_not_found(manager_instance):
    manager_instance.client.images.get.side_effect = ImageNotFound("ImageNotFound")
    manager_instance.client.images.pull.return_value = MagicMock()
    manager_instance._pull_new_image()
    manager_instance.client.images.pull.assert_called_once_with(manager_instance.new_image)


@pytest.mark.asyncio
async def test_pull_new_image_raises_critical_on_pull_error(manager_instance):
    manager_instance.client.images.get.side_effect = APIError("ImageNotFound")
    manager_instance.client.images.pull.side_effect = APIError("APIError")
    with pytest.raises(CriticalError):
        await manager_instance._pull_new_image()


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
async def test_cleanup_handles_apierror(manager_instance):
    manager_instance.client.images.remove.side_effect = APIError("APIError")
    manager_instance._cleanup("oldid")  # Should not raise


@pytest.mark.asyncio
async def test_health_check_healthy(manager_instance):
    container = MagicMock()
    container.attrs = {"State": {"Health": {"Status": "healthy"}}}
    manager_instance.client.containers.get.return_value = container
    manager_instance._health_check()  # Should not raise


@pytest.mark.asyncio
async def test_health_check_timeout(manager_instance, monkeypatch):
    container = MagicMock()
    container.attrs = {"State": {"Health": {"Status": "unhealthy"}}}
    manager_instance.client.containers.get.return_value = container
    monkeypatch.setattr("time.sleep", lambda x: None)
    monkeypatch.setattr("time.time", lambda: 0)
    # Simulate time passing
    times = [0, 10, 20, 30, 40, 50, 61]
    monkeypatch.setattr("time.time", lambda: times.pop(0))
    with pytest.raises(FallbackError):
        await manager_instance._health_check()


@pytest.mark.asyncio
async def test_swap_service_fallback_error(manager_instance):
    manager_instance._run_command = AsyncMock(side_effect=[True, False])
    with pytest.raises(FallbackError):
        await manager_instance._swap_service("cur.yml", "cand.yml")


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
    manager_instance._get_current_image_id = MagicMock(return_value="previous_image_id")
    manager_instance._pull_new_image = MagicMock()
    manager_instance._swap_service = AsyncMock()
    manager_instance._health_check = MagicMock()
    manager_instance._cleanup = MagicMock()

    logs = await manager_instance.run()

    manager_instance._run_command.assert_any_call(["git", "fetch", "origin"], cwd=ANY)
    manager_instance._run_command.assert_any_call(
        ["git", "worktree", "add", "--force", ANY, manager_instance.commit_sha], cwd=ANY
    )

    manager_instance._get_current_image_id.assert_called_once()
    manager_instance._pull_new_image.assert_called_once()
    manager_instance._swap_service.assert_awaited_once_with(ANY, ANY)
    manager_instance._health_check.assert_called_once()

    manager_instance._run_command.assert_any_call(
        ["git", "reset", "--hard", manager_instance.commit_sha], cwd=ANY
    )
    manager_instance._cleanup.assert_called_once_with("previous_image_id")

    manager_instance._run_command.assert_any_call(
        ["git", "worktree", "remove", "--force", ANY], cwd=ANY
    )
    mock_rmtree.assert_called_once_with("/tmp/mock/temp_dir", ignore_errors=True)
    assert "Deployment successful" in list(logs)[-2]


@pytest.mark.asyncio
async def test_run_rollback_on_health_check_failure(manager_instance):
    """Tests that a rollback is triggered if the health check fails."""
    manager_instance._get_current_image_id = MagicMock(return_value="previous123")
    manager_instance._pull_new_image = MagicMock()
    manager_instance._health_check = MagicMock(side_effect=FallbackError("Timeout", logs=deque()))

    # Mock _swap_service to inspect its calls
    mock_swap = AsyncMock()
    manager_instance._swap_service = mock_swap

    with pytest.raises(FallbackError):
        await manager_instance.run()

    # Assert that swap was called twice: once for deploy, once for rollback
    assert mock_swap.await_count == 2
    deploy_call, rollback_call = mock_swap.await_args_list

    # Call 1: Standard deployment
    assert deploy_call.kwargs == {}

    # Call 2: Rollback deployment
    assert rollback_call.kwargs["image_tag_override"] == "previous123"
    assert "Rollback completed" in manager_instance.logs[-2]


@pytest.mark.asyncio
async def test_run_fails_on_git_fetch(manager_instance):
    """Tests that a critical error is raised if `git fetch` fails."""
    # Return False when 'git [fetch]' is called
    manager_instance._run_command.side_effect = lambda cmd, **kwargs: cmd[1] != "fetch"

    with pytest.raises(CriticalError) as excinfo:
        await manager_instance.run()
    assert "Failed to fetch from git origin" in excinfo.value.message


@pytest.mark.asyncio
async def test_run_fails_on_worktree_creation(manager_instance):
    """Tests that a critical error is raised if `git worktree add` fails."""
    # Return False when 'git [worktree] add' is called
    manager_instance._run_command.side_effect = lambda cmd, **kwargs: cmd[1] != "worktree"

    with pytest.raises(CriticalError) as excinfo:
        await manager_instance.run()
    assert "Failed to create git worktree" in excinfo.value.message


@pytest.mark.asyncio
@patch("tempfile.mkdtemp", side_effect=PermissionError("Access denied"))
async def test_run_fails_on_tempdir_creation(mock_mkdtemp, manager_instance):
    """Tests failure when the temporary directory cannot be created."""
    with pytest.raises(CriticalError) as excinfo:
        await manager_instance.run()
    assert "Failed to create temporary directory" in excinfo.value.message
    assert "Access denied" in str(excinfo.value)


@pytest.mark.asyncio
@patch("shutil.rmtree")
async def test_run_always_cleans_up_worktree(mock_rmtree, manager_instance):
    """Ensures the worktree and temp dir are cleaned up even on failure."""
    manager_instance._pull_new_image = MagicMock(
        side_effect=CriticalError("Pull failed", logs=deque())
    )

    with pytest.raises(CriticalError):
        await manager_instance.run()

    cmds = manager_instance._run_command.call_args_list[2].args[0]
    assert cmds == [
        "git",
        "worktree",
        "remove",
        "--force",
        ANY,
    ], "Expected git worktree remove command to be called"

    mock_rmtree.assert_called_once()
