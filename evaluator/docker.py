import enum
import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .evaluation import EvaluationPaths


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


Bytes = int


class NetworkMode(enum.Enum):
    # No internet access, corresponds to `network=none`
    Isolated = 0
    # Bridged internet access
    Bridge = 1


@dataclass
class ExecutionLimits:
    # How much memory can the container use?
    memory: Bytes
    # How much disk space can the container use?
    # In bytes.
    fsize: Bytes
    # Networking mode
    network: NetworkMode

    @staticmethod
    def default() -> "ExecutionLimits":
        return ExecutionLimits(
            memory=mib(128),
            fsize=mib(128),
            network=NetworkMode.Isolated,
        )

    def update(self, update: "ExecutionLimitsUpdate") -> "ExecutionLimits":
        memory = update.memory if update.memory is not None else self.memory
        fsize = update.fsize if update.fsize is not None else self.fsize
        network = update.network if update.network is not None else self.network
        return ExecutionLimits(memory=memory, fsize=fsize, network=network)


@dataclass
class ExecutionLimitsUpdate:
    memory: Bytes | None = None
    fsize: Bytes | None = None
    network: NetworkMode | None = None


def mib(mib: Bytes) -> Bytes:
    """
    Convert MiBibytes to bytes.
    """
    return mib * (1024 * 1024)


IMAGE_LIMITS = {
    "kelvin/dotnet": ExecutionLimitsUpdate(
        network=NetworkMode.Bridge, memory=mib(512), fsize=mib(128)
    ),
    "kelvin/cargo": ExecutionLimitsUpdate(
        network=NetworkMode.Bridge, memory=mib(512), fsize=mib(128)
    ),
    "kelvin/java": ExecutionLimitsUpdate(
        network=NetworkMode.Bridge, memory=mib(512), fsize=mib(128)
    ),
    "kelvin/run": ExecutionLimitsUpdate(network=NetworkMode.Bridge, memory=mib(256), fsize=mib(16)),
    "kelvin/pythonrun": ExecutionLimitsUpdate(
        network=NetworkMode.Bridge, memory=mib(256), fsize=mib(16)
    ),
}


def create_docker_cmd(
    paths: "EvaluationPaths",
    image: DockerImage,
    additional_args: list[str] | None = None,
    cmd: list[Any] | None = None,
    custom_limits: ExecutionLimitsUpdate | None = None,
    env: dict[str, Any] | None = None,
):
    """
    Prepares a `docker run` command for execution of the given `image`.

    - `additional_args` can contain additional arguments for the `docker run` command itself.
    """
    limits = ExecutionLimits.default()
    limits = limits.update(IMAGE_LIMITS.get(image.name, ExecutionLimitsUpdate()))
    if custom_limits is not None:
        limits = limits.update(custom_limits)

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

    match limits.network:
        case NetworkMode.Bridge:
            network = "bridge"
        case _:
            network = "none"
    fsize = limits.fsize
    memory = limits.memory

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
        f"fsize={fsize}:{fsize}",
        "-m",
        f"{memory}",
        "--memory-swap",
        f"{memory}",
        "--user",
        f"{os.getuid()}",
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
