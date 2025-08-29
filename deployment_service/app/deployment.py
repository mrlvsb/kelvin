import asyncio
import logging
import os
import shutil
import tempfile
import time
from fastapi import status
from collections import deque
from pathlib import Path

import docker
from docker.errors import APIError, ImageNotFound, NotFound

HEALTH_CHECK_TIMEOUT = 60  # seconds
HEALTH_CHECK_INTERVAL = 5  # seconds


class BufferHandler(logging.Handler):
    def __init__(self, buffer: deque):
        super().__init__()
        self.buffer = buffer

    def emit(self, record):
        self.buffer.append(self.format(record))


class DeploymentException(Exception):
    """Base class for all deployment errors."""

    def __init__(self, message: str, logs: deque, status_code: int):
        self.message = message
        self.logs = logs
        self.status_code = status_code
        super().__init__(self.message)


class FallbackError(DeploymentException):
    """A recoverable error that should trigger a rollback."""

    def __init__(self, message: str, logs: deque):
        super().__init__(message, logs=logs, status_code=status.HTTP_502_BAD_GATEWAY)


class CriticalError(DeploymentException):
    """A non-recoverable error."""

    def __init__(
        self, message: str, logs: deque, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        super().__init__(message, logs=logs, status_code=status_code)


class DeploymentManager:
    """Handles the core logic of the deployment process using Git worktrees."""

    def __init__(
        self,
        service_name: str,
        image_sha: str,
        commit_sha: str,
        compose_path: Path,
        container_name: str,
        ghcr_base_url: str,
    ):
        self.service_name = service_name
        self.container_name = container_name
        self.image_sha = image_sha
        self.commit_sha = commit_sha
        self.stable_compose_path = str(compose_path)
        self.stable_repository_dir = os.path.dirname(compose_path)
        self.new_image_tag = f"{ghcr_base_url}/{self.service_name}:{self.image_sha}"
        self.client = docker.from_env()

        self.logs: deque = deque(maxlen=500)
        handler = BufferHandler(self.logs)
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        self.logger = logging.getLogger(f"deploy-{service_name}")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)

    async def _run_command(
        self, command: list[str], cwd: str, env: dict[str, str] | None = None
    ) -> bool:
        """Runs a shell command in a specified directory and logs its output."""
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        stdout, stderr = await process.communicate()
        if stdout:
            self.logger.debug(f"stdout:\n{stdout.decode()}")
        if stderr:
            self.logger.debug(f"stderr:\n{stderr.decode()}")
        return process.returncode == 0

    def _get_current_image_id(self) -> str | None:
        """Gets the image ID of the currently running container for rollback."""
        try:
            container_image = self.client.containers.get(self.container_name).image
            if not container_image:
                self.logger.warning(
                    "The image of the container not found. Rollback will not be possible."
                )
                return None
            self.logger.debug(f"Found previous image ID for rollback: {container_image.id}")
            return container_image.id
        except NotFound:
            self.logger.warning("No running container found. Rollback will not be possible.")
            return None

    def _pull_new_image(self) -> None:
        """Pulls the new Docker image from the registry."""
        self.logger.info(f"Pulling new image: {self.new_image_tag}...")
        try:
            self.client.images.pull(self.new_image_tag)
            self.logger.info("Successfully pulled new image.")
        except (ImageNotFound, APIError) as e:
            raise CriticalError(
                f"Failed to pull Docker image: {e}",
                self.logs,
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from e

    async def _swap_service(
        self,
        current_compose_file: str,
        candidate_compose_file: str,
        image_tag_override: str | None = None,
    ) -> None:
        """Stops the current service and starts a new one using a specific docker-compose file."""
        tag = image_tag_override or self.image_sha
        self.logger.info(f"Stopping service '{self.service_name}'...")
        stop_cmd = [
            "docker",
            "compose",
            "-f",
            current_compose_file,
            "--profile",
            "prod",
            "stop",
            self.service_name,
        ]
        if not await self._run_command(stop_cmd, os.path.dirname(current_compose_file)):
            self.logger.warning(
                f"Failed to stopped the service '{self.service_name}'. Is the service_name valid or first deployment?"
            )

        self.logger.info(f"Starting service with image tag: {tag}")
        up_cmd = [
            "docker",
            "compose",
            "-f",
            candidate_compose_file,
            "--profile",
            "prod",
            "up",
            "-d",
            "--no-deps",
            self.service_name,
        ]
        env = os.environ.copy()
        env[f"{self.service_name.upper()}_IMAGE_TAG"] = tag

        if not await self._run_command(up_cmd, os.path.dirname(candidate_compose_file), env=env):
            if not image_tag_override:  # Not rollback attempt
                raise FallbackError(
                    f"Failed to start the service '{self.service_name}' with candidate config.",
                    self.logs,
                )
            raise CriticalError(
                f"Failed to rollback the service '{self.service_name}'! Manual intervention required.",
                self.logs,
            )

    def _health_check(self) -> None:
        """Performs a health check on the newly started container."""
        self.logger.info("Performing health check...")
        end_time = time.time() + HEALTH_CHECK_TIMEOUT
        while time.time() < end_time:
            try:
                container = self.client.containers.get(self.container_name)
                container.reload()
                status = container.attrs.get("State", {}).get("Health", {}).get("Status")
                self.logger.info(f"Current health status: {status}")
                if status == "healthy":
                    self.logger.info("Health check passed.")
                    return
                time.sleep(HEALTH_CHECK_INTERVAL)
            except NotFound:
                self.logger.warning("Container not found during health check. Retrying...")
                time.sleep(HEALTH_CHECK_INTERVAL)
        raise FallbackError("Health check timed out.", self.logs)

    def _cleanup(self, old_image_id: str) -> None:
        """Removes the old Docker image after a successful deployment."""
        if not old_image_id:
            return
        try:
            self.client.images.remove(old_image_id, force=True)
            self.logger.info(f"Successfully removed old image: {old_image_id}")
        except APIError:
            self.logger.exception("Could not remove old image. It may be in use.")

    async def run(self) -> deque:
        """Executes the full deployment flow with a temporary Git worktree and atomic state update."""
        self.logger.info(f"Starting deployment for commit {self.commit_sha}")

        candidate_dir = tempfile.mkdtemp(prefix=f"deploy-{self.commit_sha}")
        worktree_path = os.path.join(candidate_dir, self.service_name)
        candidate_compose_path = os.path.join(
            worktree_path, os.path.basename(self.stable_compose_path)
        )

        try:
            self.logger.info("Fetching latest data from git origin...")

            if not await self._run_command(
                ["git", "fetch", "origin"], cwd=self.stable_repository_dir
            ):
                raise CriticalError(
                    "Failed to fetch from git origin. The commit might not be available.", self.logs
                )
            self.logger.info(
                f"Creating temporary worktree at {worktree_path} for commit {self.commit_sha}"
            )
            if not await self._run_command(
                ["git", "worktree", "add", "--force", worktree_path, self.commit_sha],
                cwd=self.stable_repository_dir,
            ):
                raise CriticalError(
                    "Failed to create git worktree. Is the commit SHA valid?", self.logs
                )

            previous_image_id = self._get_current_image_id()
            self._pull_new_image()

            self.logger.info(f"Deploying service using config from commit {self.commit_sha}")
            await self._swap_service(self.stable_compose_path, candidate_compose_path)

            self._health_check()

            self.logger.info(f"Updating stable configuration to commit {self.commit_sha}")
            if not await self._run_command(
                ["git", "reset", "--hard", self.commit_sha], cwd=self.stable_repository_dir
            ):
                self.logger.error(
                    "Service is running, but failed to update stable git state!"
                )  # TODO: Try to handle RuntimeError better?

            if previous_image_id:
                self._cleanup(previous_image_id)
            self.logger.info(f"Deployment successful for {self.service_name}:{self.image_sha}")
            return self.logs
        except FallbackError as e:
            self.logger.error(f"An error occurred: {e} Initiating rollback.")
            if previous_image_id:
                rollback_tag = previous_image_id.split(":")[-1]
                await self._swap_service(
                    candidate_compose_path,
                    self.stable_compose_path,
                    image_tag_override=rollback_tag,
                )
                self.logger.info("Rollback completed successfully.")
            else:
                self.logger.error("No previous image ID available. Cannot perform rollback.")
            raise e
        except Exception as e:
            raise CriticalError(f"Unexpected deployment failure: {e}", self.logs) from e
        finally:
            # ALWAYS clean up the worktree, no matter what happened.
            self.logger.info("Cleaning up temporary worktree...")
            await self._run_command(
                ["git", "worktree", "remove", "--force", worktree_path],
                cwd=self.stable_repository_dir,
            )
            shutil.rmtree(candidate_dir, ignore_errors=True)
