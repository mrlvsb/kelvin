import os
import shlex
import html
import subprocess
import logging
import json
import bleach
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CompileResult:
    success: bool
    html: str

@dataclass
class DockerCommandResult:
    returncode: int
    stdout: str
    stderr: str

class TypeHandler:
    def __init__(self, pipeline_config: dict[str, Any], evaluation: Any):
        self.config = pipeline_config
        self.evaluation = evaluation

    def compile(self, container_image: str) -> CompileResult:
        """
        Runs the compilation/linting step.
        Returns CompileResult(success, html_output).
        """
        return CompileResult(True, "")

    def _run_docker_command(self, image: str, cmd: list[str], env: dict[str, str] | None = None) -> DockerCommandResult:
        """
        Helper to run a command in a docker container.

        Mounting Explanation:
        We mount the host's submission directory (self.evaluation.submit_path)
        to /work inside the container.

        - self.evaluation.submit_path: Absolute path on the host where student files are.
        - /work: Standardized path inside the container.
        - -w /work: Sets the current working directory to /work.

        This means tools like 'gcc' or 'cargo' running inside will see the student's
        files in the current directory, regardless of where they are stored on the host.
        """
        if env is None:
            env = {}

        # Prepare docker command
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "-w", "/work",
            "-v", f"{self.evaluation.submit_path}:/work",
            "--user", str(os.getuid()),
        ]

        # Add environment variables
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
                timeout=300, # 5 minutes global timeout for compile
            )
            return DockerCommandResult(
                returncode=result.returncode, 
                stdout=result.stdout.decode('utf-8', errors='replace'), 
                stderr=result.stderr.decode('utf-8', errors='replace')
            )
        except subprocess.TimeoutExpired:
            return DockerCommandResult(-1, "", "Compilation timed out")
        except Exception as e:
            return DockerCommandResult(-1, "", f"Error running docker: {e}")

    def _sanitize(self, text: str) -> str:
        return bleach.clean(text)

    def _format_command_output(self, cmd_str: str, output: str) -> str:
        """Helper to format command execution for the HTML report"""
        html_out = f"<code style='filter: opacity(.7);'>$ {html.escape(cmd_str)}</code>"
        if output:
            html_out += f"<kelvin-terminal-output>{html.escape(output)}</kelvin-terminal-output>"
        return html_out

class Gcc(TypeHandler):
    def compile(self, container_image: str) -> CompileResult:
        flags = self.config.get("flags", "")
        ldflags = self.config.get("ldflags", "")
        cmakeflags = self.config.get("cmakeflags", "[]") # Json string in config
        makeflags = self.config.get("makeflags", "[]")   # Json string in config
        output_bin = self.config.get("output", "main")
        
        html_chunks = []
        
        # Determine what build system to use
        files = [f.lower() for f in os.listdir(self.evaluation.submit_path)]
        
        env = {
            "CC": "gcc",
            "CXX": "g++",
            "CFLAGS": flags,
            "CXXFLAGS": flags,
            "LDFLAGS": ldflags,
            "CLICOLOR_FORCE": "1",
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        }

        # 1. CMake
        if "cmakelists.txt" in files:
            try:
                c_flags_parsed = json.loads(cmakeflags)
            except Exception:
                c_flags_parsed = []
                
            cmd = ["cmake", *c_flags_parsed, "."]
            res = self._run_docker_command(container_image, cmd, env)
            html_chunks.append(self._format_command_output("cmake " + " ".join(c_flags_parsed) + " .", res.stdout + res.stderr))
            
            if res.returncode != 0:
                html_chunks.append(f"<div style='color: red'>Could not run CMake, exit code {res.returncode}</div>")
                return CompileResult(False, "".join(html_chunks))

        # 2. Make
        if "makefile" in files:
            try:
                m_flags_parsed = json.loads(makeflags)
            except Exception:
                m_flags_parsed = []
                
            cmd = ["make", *m_flags_parsed]
            res = self._run_docker_command(container_image, cmd, env)
            html_chunks.append(self._format_command_output("make " + " ".join(m_flags_parsed), res.stdout + res.stderr))
            
            if res.returncode != 0:
                html_chunks.append(f"<div style='color: red'>Could not run Make, exit code {res.returncode}</div>")
                return CompileResult(False, "".join(html_chunks))
        else:
            # 3. Direct GCC/G++ invocation
            sources = []
            for root, dirs, filenames in os.walk(self.evaluation.submit_path):
                for f in filenames:
                    if f.split(".")[-1] in ["c", "cpp"]:
                        # We use relative path for docker execution
                        rel_dir = os.path.relpath(root, self.evaluation.submit_path)
                        if rel_dir == ".":
                            sources.append(f)
                        else:
                            sources.append(os.path.join(rel_dir, f))
            
            if not sources:
                 html_chunks.append("<div style='color: red'>Missing source files! please upload .c or .cpp files!</div>")
                 return CompileResult(False, "".join(html_chunks))

            use_cpp = any(f.endswith(".cpp") for f in sources)
            compiler = "g++" if use_cpp else "gcc"
            
            cmd = [compiler] + sources + ["-o", output_bin] + shlex.split(flags) + shlex.split(ldflags)
            
            res = self._run_docker_command(container_image, cmd, env)
            html_chunks.append(self._format_command_output(" ".join(cmd), res.stdout + res.stderr))
            
            if res.returncode != 0:
                html_chunks.append(f"<div style='color: red'>Failed to run GCC, exit code {res.returncode}</div>")
                return CompileResult(False, "".join(html_chunks))
        
        if res.returncode == 0:
            html_chunks.append("<div style='color: green'>Compilation succeeded</div>")

        return CompileResult(True, "".join(html_chunks))
