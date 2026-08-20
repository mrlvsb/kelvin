import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any

from .evaluation import EvaluationPaths
from .utils import parse_human_size


@dataclass
class DockerImage:
    name: str
    version: str

    def full_name(self) -> str:
        return f"{self.name}:{self.version}"


def prepare_docker_image(name: str, before: list[str] | None = None) -> DockerImage:
    """
    Prepares a Docker container for execution and returns its name.
    `before` can be a list of commands that will be executed on top of the baseline image with the
    given `name`.
    """
    image = normalize_docker_image(name)

    if not before:
        return image

    name = image.full_name()
    hash = hashlib.md5((name + "\n".join(before)).encode("utf-8")).hexdigest()
    target_image = DockerImage(name=image.name, version=hash)
    target_name = target_image.full_name()

    instructions = [f"FROM {name}"] + [f"RUN {cmd}" for cmd in before]

    logging.warning(f"Building image {target_name}")
    try:
        subprocess.check_output(
            ["docker", "build", "-", "-t", target_name],
            input="\n".join(instructions),
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        if "pull access denied for" in e.output:
            raise ImageNotFoundException(name)
        raise Exception(e.output)
    return target_image


DEFAULT_LIMITS = {"fsize": "16M", "memory": "128M", "network": "none"}

IMAGE_LIMITS = {
    "kelvin/dotnet": {
        "network": "bridge",
        "memory": "512M",
        "fsize": "128M",
    },
    "kelvin/cargo": {
        "network": "bridge",
        "memory": "512M",
        "fsize": "128M",
    },
    "kelvin/java": {
        "network": "bridge",
        "memory": "512M",
        "fsize": "128M",
    },
    "kelvin/run": {
        "network": "bridge",
        "memory": "256M",
        "fsize": "16M",
    },
    "kelvin/pythonrun": {
        "network": "bridge",
        "memory": "256M",
        "fsize": "16M",
    },
}


def create_docker_cmd(
    paths: EvaluationPaths,
    image: DockerImage,
    additional_args: list[str] | None = None,
    cmd: list[Any] | None = None,
    limits: dict[str, Any] | None = None,
    env: dict[str, Any] | None = None,
):
    """
    Prepares a `docker run` command for execution of the given `image`.

    - `additional_args` can contain additional arguments for the `docker run` command itself.
    """
    if not limits:
        limits = {}
    limits = {**DEFAULT_LIMITS, **IMAGE_LIMITS.get(image.name, {}), **limits}
    for k, v in limits.items():
        if k in ("fsize", "memory"):
            limits[k] = parse_human_size(v)

    if not cmd:
        cmd = []

    cmd = [str(arg) for arg in cmd]

    if not env:
        env = {}

    if not additional_args:
        additional_args = []

    def fmt_value(v):
        if isinstance(v, list):
            return json.dumps(v)
        return v

    env = [f"-ePIPE_{k.upper()}={fmt_value(v)}" for k, v in env.items()]

    template_path = os.path.join("", paths.task_dir, "template")
    if os.path.isdir(template_path):
        additional_args.append("-v")
        additional_args.append(f"{template_path}:/template:ro")

    network = limits["network"]
    # Forcefully disable using --network=host
    if network == "host":
        network = "bridge"
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        network,
        "-w",
        "/work",
        "-v",
        f"{paths.submit_dir}:/work",
        "--ulimit",
        f'fsize={limits["fsize"]}:{limits["fsize"]}',
        "-m",
        str(limits["memory"]),
        "--memory-swap",
        str(limits["memory"]),
        "--user",
        str(os.getuid()),
        "-i",
        *additional_args,
        *env,
        image.full_name(),
        *cmd,
    ]


class ImageNotFoundException(BaseException):
    pass


def normalize_docker_image(name: str) -> DockerImage:
    """
    Normalizes a string containing a Docker image.
    It can be just the name (e.g. `kelvin/run`) or it can also contain the tag (`kelvin/run:foo`).
    If the tag is missing, latest will be used.
    """
    parts = name.split(":")
    basename = parts[0]
    version = "latest" if len(parts) == 1 else parts[1]
    return DockerImage(name=basename, version=version)
