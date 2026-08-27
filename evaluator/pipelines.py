import hashlib
import json
import logging
import os
import subprocess

from .utils import parse_human_size

logger = logging.getLogger("evaluator")

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


def create_docker_cmd(evaluation, image, additional_args=None, cmd=None, limits=None, env=None):
    if not limits:
        limits = {}
    limits = {**DEFAULT_LIMITS, **IMAGE_LIMITS.get(image.split(":")[0], {}), **limits}
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

    template_path = os.path.join("", evaluation.task_path, "template")
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
        evaluation.submit_path + ":/work",
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
        image,
        *cmd,
    ]


def docker_image(name):
    parts = name.split(":")
    basename = parts[0]
    version = "latest" if len(parts) == 1 else parts[1]
    return f"{basename}:{version}"


class ImageNotFoundException(Exception):
    pass


def prepare_container(name, before=None):
    if not before:
        return name

    hash = hashlib.md5((name + "\n".join(before)).encode("utf-8")).hexdigest()
    base_name = name.split(":")[0]
    target_name = f"{base_name}:{hash}"

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
    return target_name


class DockerPipe:
    def __init__(self, image, limits=None, before=None, **kwargs):
        self.image = image
        self.kwargs = kwargs
        self.limits = limits
        self.before = [] if not before else before

    def run(self, evaluation):
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        image = prepare_container(docker_image(self.image), self.before)
        args = create_docker_cmd(evaluation, image, env=self.kwargs, limits=self.limits)

        def res_path(p):
            return os.path.join(result_dir, p)

        with open(res_path("stdout"), "w") as stdout, open(res_path("stderr"), "w") as stderr:
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            p.communicate()

        result = {}
        try:
            json_result_path = os.path.join(evaluation.submit_path, "piperesult.json")
            if os.path.islink(json_result_path):
                raise FileNotFoundError
            with open(json_result_path) as f:
                result = json.load(f)
        except FileNotFoundError:
            pass

        with open(res_path("stdout")) as stdout, open(res_path("stderr")) as stderr:
            print(stdout.read())
            print(stderr.read())

        if "failed" not in result:
            result["failed"] = p.returncode != 0

        try:
            path = os.path.join(evaluation.submit_path, "result.html")
            if os.path.islink(path):
                raise FileNotFoundError
            with open(path) as f:
                result["html"] = f.read()
            os.unlink(path)
        except FileNotFoundError:
            pass

        for f in ["stdout", "stderr"]:
            if os.path.getsize(res_path(f)) == 0:
                os.unlink(res_path(f))
        if not os.listdir(result_dir):
            os.rmdir(result_dir)

        return result
