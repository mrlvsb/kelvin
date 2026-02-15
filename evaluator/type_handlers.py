import os
import shlex
import subprocess
import logging
import json
from functools import cached_property
from pathlib import Path

import nh3

from collections import defaultdict
from typing import Any, Optional
from dataclasses import dataclass, field

from evaluator.utils import parse_human_size

logger = logging.getLogger(__name__)


@dataclass
class Comment:
    line: int
    text: str
    source: str
    file: str
    url: Optional[str] = None


@dataclass
class BuildResult:
    success: bool
    html: str
    comments: list[Comment] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)

    @property
    def simple_comments(self) -> dict[str, list[dict]]:
        """
        Returns comments in the format expected by piperesult.json:
        {
            "filename": [
                {"line": 1, "text": "...", "source": "..."},
                ...
            ]
        }
        """
        out = defaultdict(list)
        for c in self.comments:
            out[c.file].append(
                {
                    "line": c.line,
                    "text": c.text,
                    "source": c.source,
                    "url": c.url,
                }
            )
        return dict(out)

    @staticmethod
    def fail(html_error: str) -> "BuildResult":
        return BuildResult(False, html_error)


@dataclass
class DockerCommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class ExecutionLimits:
    time: int = 300  # seconds
    memory: str = "128M"
    fsize: str = "16M"
    network: str = "none"


@dataclass
class BuildCommand:
    cmd: list[str]
    env: dict[str, str] = field(default_factory=dict)
    output_dir: Optional[str] = None


class BuildError(Exception):
    def __init__(self, message: str, logs: str = ""):
        self.message = nh3.clean_text(message)
        self.logs = nh3.clean_text(logs)


class TypeHandler:
    def __init__(self, pipeline_config: dict[str, Any], evaluation: Any, limits: ExecutionLimits):
        """
        Initialize the TypeHandler.

        Args:
            pipeline_config: The dictionary from the YAML configuration for this pipeline step.
            evaluation: The evaluation context object containing paths/metadata.
            limits: The resolved ExecutionLimits object.
        """
        self.config = pipeline_config
        self.evaluation = evaluation
        self.limits = limits

    def compile(self, container_image: str) -> BuildResult:
        """
        Runs the compilation/linting step.
        Returns BuildResult(success, html_output).
        """
        try:
            return self._compile(container_image)
        except BuildError as e:
            html = e.logs + f"<div style='color: red'>{e.message}</div>"
            return BuildResult.fail(html)

    def _compile(self, container_image: str) -> BuildResult:
        raise NotImplementedError

    def _run_docker_command(
        self, image: str, cmd: list[str], env: dict[str, str] | None = None
    ) -> DockerCommandResult:
        """
        Helper to run a command in a docker container.

        Mounts:
        - /work: Student submission (read-write)
        - /template: Teacher provided template files (read-only), if present.
        """
        if env is None:
            env = {}

        # 1. Base Docker Run Arguments
        # --rm: Remove container after exit
        # --user: Run as the current user (uid) to avoid permission issues with mapped files
        # -w /work: Set working directory
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--user",
            str(os.getuid()),
            "-w",
            "/work",
        ]

        # 2. Network Configuration
        # Forcefully disable using --network=host for security
        network_mode = self.limits.network
        if network_mode == "host":
            network_mode = "bridge"
        docker_cmd.extend(["--network", network_mode])

        # 3. Resource Limits
        # ulimit: Restricts file size created by the process
        # memory/memory-swap: Restricts RAM usage
        # Note: ulimit fsize usually requires integer (bytes or blocks), so we parse it.
        # Docker -m accepts strings like "128M".
        fsize_bytes = parse_human_size(self.limits.fsize)
        docker_cmd.extend(
            [
                "--ulimit",
                f"fsize={fsize_bytes}:{fsize_bytes}",
                "-m",
                self.limits.memory,
                "--memory-swap",
                self.limits.memory,
            ]
        )

        # 4. Mounts
        # 4a. Submission Mount
        docker_cmd.extend(["-v", f"{self.evaluation.submit_path}:/work"])

        # 4b. Template Mount
        # This allows separation of student code vs immutable teacher code (headers, data).
        template_path = os.path.join(self.evaluation.task_path, "template")
        if os.path.isdir(template_path):
            docker_cmd.extend(["-v", f"{template_path}:/template:ro"])

        for k, v in env.items():
            docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.append(image)
        docker_cmd.extend(cmd)

        logger.info(f"Executing: {' '.join(docker_cmd)}")

        try:
            # We use subprocess.run to capture output
            result = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.limits.time,
            )
            return DockerCommandResult(
                returncode=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
            )
        except subprocess.TimeoutExpired:
            return DockerCommandResult(-1, "", "Compilation timed out")
        except Exception as e:
            return DockerCommandResult(-1, "", f"Error running docker: {e}")

    def _format_html_generic(
        self,
        cmd: list[str],
        stdout: str,
        stderr: str,
        returncode: int,
        message: Optional[str] = None,
    ) -> str:
        cmd_str = nh3.clean_text(" ".join(cmd))
        html_out = f"<code style='filter: opacity(.7);'>$ {cmd_str}</code>"

        safe_out = nh3.clean_text(stdout.strip())
        safe_err = nh3.clean_text(stderr.strip())
        safe_msg = nh3.clean_text(message) if message else None

        content = ""

        if safe_err:
            if returncode == 0:
                content += f"<details><summary>Stderr</summary>{safe_err}</details>"
                if safe_out:
                    content += "\n"
            else:
                # Show stderr openly on failure
                content += f"{safe_err}"
                if safe_out:
                    content += "\n"

        if safe_out:
            content += safe_out

        if content:
            html_out += f"<kelvin-terminal-output>{content}</kelvin-terminal-output>"

        if returncode == 0:
            if safe_msg:
                html_out += f"<div style='color: green'>{safe_msg} (Exit code: {returncode})</div>"
            else:
                html_out += (
                    f"<div style='color: green'>Build successful (Exit code: {returncode})</div>"
                )
        else:
            if safe_msg:
                html_out += f"<div style='color: red'>{safe_msg} (Exit code: {returncode})</div>"
            else:
                html_out += f"<div style='color: red'>Build failed (Exit code: {returncode})</div>"
        return html_out


class Gcc(TypeHandler):
    @cached_property
    def _common_env(self) -> dict[str, str]:
        flags = self.config.get("flags", "")
        ldflags = self.config.get("ldflags", "")
        return {
            "CC": "gcc",
            "CXX": "g++",
            "CFLAGS": flags,
            "CXXFLAGS": flags,
            "LDFLAGS": ldflags,
            "CLICOLOR_FORCE": "1",
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        }

    def _compile(self, container_image: str) -> BuildResult:
        build_cmds = self._build_command()

        html_output = ""

        for i, bcmd in enumerate(build_cmds):
            res = self._run_docker_command(container_image, bcmd.cmd, bcmd.env)

            # Determine message based on command type (heuristics)
            msg = None
            if bcmd.cmd[0] == "cmake":
                if len(bcmd.cmd) > 1 and bcmd.cmd[1] == "--build":
                    msg = "Build succeeded" if res.returncode == 0 else "Build failed"
                else:
                    msg = (
                        "CMake configuration succeeded"
                        if res.returncode == 0
                        else "Could not run CMake"
                    )
            elif bcmd.cmd[0] == "make":
                msg = "Make succeeded" if res.returncode == 0 else "Could not run Make"
            elif bcmd.cmd[0].endswith("gcc") or bcmd.cmd[0].endswith("g++"):
                msg = "Compilation succeeded" if res.returncode == 0 else "Failed to run GCC"

            html_output += self._format_html_generic(
                bcmd.cmd, res.stdout, res.stderr, res.returncode, message=msg
            )

            if res.returncode != 0:
                # Return immediately if build command fails
                # We return BuildResult directly here as it is not a "check" failure but a "run" failure
                return BuildResult.fail(html_output)

        # Find any new executable and rename it to the expected output
        output_bin = self.config.get("output", "main")
        output_path = os.path.join(self.evaluation.submit_path, output_bin)

        if not os.path.exists(output_path):
            executables = []
            for f in os.listdir(self.evaluation.submit_path):
                fpath = os.path.join(self.evaluation.submit_path, f)
                if os.access(fpath, os.X_OK) and not os.path.isdir(fpath):
                    executables.append(f)

            if len(executables) == 0:
                raise BuildError("No executable has been built.", logs=html_output)
            elif len(executables) > 1:
                raise BuildError(
                    f"Multiple executables have been built: {','.join(executables)}",
                    logs=html_output,
                )
            else:
                # Rename found executable to output
                src = os.path.join(self.evaluation.submit_path, executables[0])
                os.rename(src, output_path)

                # Fake the mv command log using generic formatter
                html_output += self._format_html_generic(
                    ["mv", executables[0], output_bin],
                    "",
                    "",
                    0,
                    message="Artifact moved and renamed",
                )

        return BuildResult(True, html_output)

    def _build_command(self) -> list[BuildCommand]:
        files = [f.lower() for f in os.listdir(self.evaluation.submit_path)]
        env = self._common_env

        if "cmakelists.txt" in files:
            cmakeflags = self.config.get("cmakeflags", "[]")
            try:
                c_flags_parsed = json.loads(cmakeflags)
            except Exception:
                c_flags_parsed = []

            # 1. Configure
            cmd_conf = BuildCommand(["cmake", *c_flags_parsed, "."], env)
            # 2. Build
            cmd_build = BuildCommand(["cmake", "--build", "."], env)
            return [cmd_conf, cmd_build]

        if "makefile" in files:
            makeflags = self.config.get("makeflags", "[]")
            try:
                m_flags_parsed = json.loads(makeflags)
            except Exception:
                m_flags_parsed = []
            return [BuildCommand(["make", *m_flags_parsed], env)]

        # GCC fallback
        output_bin = self.config.get("output", "main")
        flags = self.config.get("flags", "")
        ldflags = self.config.get("ldflags", "")

        sources = []
        for root, dirs, filenames in os.walk(self.evaluation.submit_path):
            for f in filenames:
                suffix = Path(f).suffix
                if suffix in (".c", ".cpp", ".cc", ".cxx"):
                    # We use relative path for docker execution
                    rel_dir = os.path.relpath(root, self.evaluation.submit_path)
                    if rel_dir == ".":
                        sources.append(f)
                    else:
                        sources.append(os.path.join(rel_dir, f))

        if not sources:
            raise BuildError("Missing source files! please upload .c or .cpp files!")

        use_cpp = any(Path(f).suffix in (".cpp", ".cc", ".cxx") for f in sources)
        compiler = "g++" if use_cpp else "gcc"

        cmd = [compiler] + sources + ["-o", output_bin] + shlex.split(flags) + shlex.split(ldflags)
        return [BuildCommand(cmd, env)]
