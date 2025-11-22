import asyncio
import logging
import os
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path

import docker
import httpx
from docker.errors import APIError, ImageNotFound, NotFound
from fastapi import status

from app.config import get_settings

HEALTH_CHECK_TIMEOUT = 90  # seconds
HEALTH_CHECK_INTERVAL = 5  # seconds


class BufferHandler(logging.Handler):
    def __init__(self, buffer: deque):
        super().__init__()
        self.buffer = buffer

    def emit(self, record):
        self.buffer.append(self.format(record))


class DeploymentError(Exception):
    """Base class for all deployment errors."""

    def __init__(self, message: str, logs: deque, status_code: int):
        self.message = message
        self.logs = logs
        self.status_code = status_code
        super().__init__(self.message)


class FallbackError(DeploymentError):
    """A recoverable error that should trigger a rollback."""

    def __init__(self, message: str, logs: deque):
        super().__init__(message, logs=logs, status_code=status.HTTP_502_BAD_GATEWAY)


class CriticalError(DeploymentError):
    """A non-recoverable error."""

    def __init__(
        self, message: str, logs: deque, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        super().__init__(message, logs=logs, status_code=status_code)


class DeploymentManager:
    """Handles the core logic of the deployment process using candidate docker-compose.yml."""

    def __init__(
        self,
        service_name: str,
        image: dict[str, str],
        commit_sha: str,
        compose_path: Path,
        compose_env_file: Path | None,
        container_name: str,
        healthcheck_url: str,
    ):
        self.service_name = service_name
        self.container_name = container_name
        self.healthcheck_url = healthcheck_url
        self.image_tag = image["tag"]
        self.commit_sha = commit_sha
        self.stable_compose_path = str(compose_path.resolve())
        self.stable_compose_env_file = str(
            compose_env_file or compose_path.resolve().parent / ".env"
        )
        self.stable_repository_dir = compose_path.resolve().parent
        repo = image.get("repository")
        self.new_image = f"{repo + '/' if repo else ''}{image['image']}:{self.image_tag}"
        self.client = docker.from_env()

        self.logs: deque = deque(maxlen=500)
        handler = BufferHandler(self.logs)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(handler)

    async def _run_command(
        self,
        command: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        output_file: str | None = None,
    ) -> bool:
        """Runs a shell command in a specified directory and logs its output."""
        if output_file:
            with open(output_file, "w") as f:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=cwd,
                    env=env,
                    stdout=f,
                    stderr=f,
                )
                await process.wait()
        else:
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

    def _get_current_image(self) -> tuple[str, str] | tuple[None, None]:
        """Gets an image tag corresponding to the commit SHA of the currently running container
        for rollback."""
        try:
            container_image = self.client.containers.get(self.container_name).image
            if not container_image:
                self.logger.error(
                    "The image of the container not found. Rollback will not be possible."
                )
                return None, None
            tags = [t.split(":")[-1] for t in container_image.tags]
            tags = sorted(t for t in tags if t != "latest")
            container_image_id = str(container_image.id).split(":")[-1]
            if not tags:
                self.logger.error(
                    f"A tag for image {container_image} was not found. Using image ID {container_image.id} as a fallback."
                )
                return container_image_id, container_image_id
            self.logger.debug(f"Found previous image tag for rollback: {tags[0]}")
            return tags[0], container_image_id
        except NotFound:
            self.logger.error("No running container found. Rollback will not be possible.")
            return None, None

    def _pull_new_image(self) -> None:
        """Pulls the new Docker image from the registry."""
        self.logger.info(f"Pulling new image: {self.new_image}...")
        try:
            image = self.client.images.get(self.new_image)
            self.logger.info(f"Image {self.new_image} already exists locally: {image.id}")
        except (ImageNotFound, APIError):
            try:
                self.client.images.pull(self.new_image)
                self.logger.info("Successfully pulled new image.")
            except (ImageNotFound, APIError) as e:
                raise CriticalError(
                    f"Failed to pull Docker image: {e}",
                    self.logs,
                    status.HTTP_400_BAD_REQUEST,
                ) from e

    async def _watch_container_logs(self, stop_logs: asyncio.Event) -> None:
        """
        Background task: reconnects to container logs and streams new lines
        into self.logs. It runs until stop_logs is set.
        """
        self.logger.info("Connecting to container to stream logs...")

        loop = asyncio.get_event_loop()

        def blocking_reader(container):
            try:
                for chunk in container.logs(stream=True, follow=True, tail=0):
                    line = chunk.decode(errors="replace")
                    self.logger.info(f"[Container] {line}")
                    if stop_logs.is_set():
                        break
            except Exception as e:
                self.logger.debug(f"Container log reader exception: {e}")

        while not stop_logs.is_set():
            try:
                container = self.client.containers.get(self.container_name)
            except NotFound:
                # Container not running yet, wait and retry
                await asyncio.sleep(0.5)
                continue

            # Run the blocking reader in executor, returns when container log stream ends
            await loop.run_in_executor(None, blocking_reader, container)

            # Small pause before reconnecting (container might be restarting)
            await asyncio.sleep(0.2)

        self.logger.info("Disconnected from container log stream.")

    async def _swap_service(
        self,
        current_compose_file: str,
        candidate_compose_file: str,
        image_tag_override: str | None = None,
    ) -> bool:
        """Stops the current service and starts a new one using a specific docker-compose file."""
        tag = image_tag_override or self.image_tag
        self.logger.info(f"Stopping service '{self.service_name}'...")
        stop_cmd = [
            "docker",
            "compose",
            "--env-file",
            self.stable_compose_env_file,
            "-f",
            current_compose_file,
            "--profile",
            "prod",
            "stop",
            self.service_name,
        ]
        if not await self._run_command(stop_cmd, self.stable_repository_dir):
            self.logger.warning(
                f"Failed to stopped the service '{self.service_name}'. Is the service_name valid or first deployment?"
            )

        self.logger.info(f"Starting service with image tag: {tag}")
        up_cmd = [
            "docker",
            "compose",
            "--env-file",
            self.stable_compose_env_file,
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
        if not await self._run_command(up_cmd, self.stable_repository_dir, env=env):
            if not image_tag_override:  # Non-rollback attempt
                self.logger.error(
                    f"Failed to start the service '{self.service_name}' with candidate config."
                )
                return False
            raise CriticalError(
                f"Failed to rollback the service '{self.service_name}'! Manual intervention required.",
                self.logs,
            )
        return True

    async def _health_check(self) -> bool:
        """Performs a health check by making HTTP requests to a specified URL."""
        self.logger.info(f"Performing health check on {self.healthcheck_url}...")
        end_time = time.time() + HEALTH_CHECK_TIMEOUT
        async with httpx.AsyncClient(verify=not get_settings().debug) as client:
            while time.time() < end_time:
                try:
                    response = await client.get(self.healthcheck_url, timeout=2.0)
                    self.logger.info(f"Health check response status: {response.status_code}")
                    if response.status_code == 200:
                        self.logger.info("Health check passed.")
                        return True
                except httpx.RequestError as exc:
                    self.logger.warning(f"Health check request failed: {exc}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        self.logger.error("Health check timed out.")
        return False

    def _cleanup(self, old_image_id: str) -> None:
        """Removes the old Docker image after a successful deployment."""
        if not old_image_id or old_image_id == self.image_tag:
            return None
        try:
            self.client.images.remove(old_image_id, force=True)
            self.logger.info(f"Successfully removed old image: {old_image_id}")
        except APIError as e:
            self.logger.error(f"Could not remove old image. It may be in use. Error: {e}")

    async def run(self) -> deque:
        """Executes the full deployment flow with a temporary candidate of docker-compose.yml and atomic state update."""
        self.logger.info(f"Starting deployment for commit {self.commit_sha}")
        try:
            candidate_dir = tempfile.mkdtemp(prefix=f"deploy-{self.commit_sha}")
        except OSError as e:
            raise CriticalError(f"Failed to create temporary directory: {e}", self.logs) from e

        candidate_compose_path = os.path.join(
            candidate_dir, os.path.basename(self.stable_compose_path)
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
                f"Copying candidate docker-compose.yml file at {candidate_dir} for commit {self.commit_sha}"
            )
            if not await self._run_command(
                [
                    "git",
                    "show",
                    f"{self.commit_sha}:{os.path.basename(self.stable_compose_path)}",
                ],
                cwd=self.stable_repository_dir,
                output_file=candidate_compose_path,
            ):
                raise CriticalError(
                    "Failed to create candidate docker-compose.yml file. Is the commit SHA valid?",
                    self.logs,
                )

            previous_image_tag, previous_image_id = self._get_current_image()
            self._pull_new_image()

            stop_container_logs = asyncio.Event()
            container_logs_task = asyncio.create_task(
                self._watch_container_logs(stop_container_logs)
            )

            self.logger.info(f"Deploying service using config from commit {self.commit_sha}")
            deployment_successful = False
            if (
                await self._swap_service(self.stable_compose_path, candidate_compose_path)
                and await self._health_check()
            ):
                deployment_successful = True
            if not deployment_successful:
                self.logger.info(
                    f"Initiating rollback to previous image tag or id: {previous_image_tag}"
                )
                if previous_image_tag:
                    await self._swap_service(
                        candidate_compose_path,
                        self.stable_compose_path,
                        image_tag_override=previous_image_tag,
                    )
                    self.logger.info("Rollback completed successfully.")
                else:
                    self.logger.error("No previous image ID available. Cannot perform rollback.")

                raise FallbackError(
                    f"Service '{self.service_name}' failed to start with candidate config or health check failed.",
                    self.logs,
                )

            self.logger.info(f"Updating stable configuration to commit {self.commit_sha}")
            if not await self._run_command(
                ["git", "reset", "--hard", self.commit_sha], cwd=self.stable_repository_dir
            ):
                self.logger.error(
                    "Service is running, but failed to update stable git state!"
                )  # TODO: Try to handle RuntimeError better?

            if previous_image_id:
                self._cleanup(previous_image_id)
            self.logger.info(f"Deployment successful for {self.service_name}:{self.image_tag}")
            return self.logs
        except FallbackError as e:
            raise e
        except CriticalError as e:
            self.logger.error(f"{e}. Deployment aborted.")
            raise e
        except Exception as e:
            raise CriticalError(f"Unexpected deployment failure: {e}", self.logs) from e
        finally:
            stop_container_logs.set()
            try:
                await asyncio.wait_for(container_logs_task, timeout=5.0)
            except TimeoutError:
                self.logger.debug("Log streaming task did not finish in time and was cancelled.")
            # ALWAYS clean up the temporary directory, no matter what happened.
            self.logger.info("Cleaning up temporary directory...")
            shutil.rmtree(candidate_dir, ignore_errors=True)
