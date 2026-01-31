import os
import shlex
import html
import subprocess
import logging
import json
import bleach
import glob
import re
from pathlib import Path
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
            out[c.file].append({
                "line": c.line,
                "text": c.text,
                "source": c.source
            })
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
    time: int = 300 # seconds
    memory: str = "128M"
    fsize: str = "16M"
    network: str = "none"

@dataclass
class BinaryArtifact:
    name: str
    path: str

@dataclass
class CargoOutput:
    stdout: str
    stderr: str
    comments: list[Comment]
    binary_artifacts: list[BinaryArtifact]

@dataclass
class ProjectFileResult:
    path: Optional[str] = None
    error: Optional[str] = None

@dataclass
class BuildCommand:
    cmd: list[str]
    env: dict[str, str]
    output_dir: str

@dataclass
class ParseOutputResult:
    comments: list[Comment]
    tests: list[dict]

@dataclass
class CargoLocation:
    file: str
    line: int

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
        return BuildResult(True, "")

    def _run_docker_command(self, image: str, cmd: list[str], env: dict[str, str] | None = None) -> DockerCommandResult:
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
            "docker", "run", "--rm",
            "--user", str(os.getuid()),
            "-w", "/work",
        ]

        # 2. Network Configuration
        network_mode = self.limits.network
        docker_cmd.extend(["--network", network_mode])

        # 3. Resource Limits
        # ulimit: Restricts file size created by the process
        # memory/memory-swap: Restricts RAM usage
        # Note: ulimit fsize usually requires integer (bytes or blocks), so we parse it.
        # Docker -m accepts strings like "128M".
        fsize_bytes = parse_human_size(self.limits.fsize)
        docker_cmd.extend([
            "--ulimit", f"fsize={fsize_bytes}:{fsize_bytes}",
            "-m", self.limits.memory,
            "--memory-swap", self.limits.memory, 
        ])

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
    def compile(self, container_image: str) -> BuildResult:
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
                return BuildResult(False, "".join(html_chunks))

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
                return BuildResult(False, "".join(html_chunks))
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
                 return BuildResult(False, "".join(html_chunks))

            use_cpp = any(f.endswith(".cpp") for f in sources)
            compiler = "g++" if use_cpp else "gcc"
            
            cmd = [compiler] + sources + ["-o", output_bin] + shlex.split(flags) + shlex.split(ldflags)
            
            res = self._run_docker_command(container_image, cmd, env)
            html_chunks.append(self._format_command_output(" ".join(cmd), res.stdout + res.stderr))
            
            if res.returncode != 0:
                html_chunks.append(f"<div style='color: red'>Failed to run GCC, exit code {res.returncode}</div>")
                return BuildResult(False, "".join(html_chunks))
        
        if res.returncode == 0:
            html_chunks.append("<div style='color: green'>Compilation succeeded</div>")

        return BuildResult(True, "".join(html_chunks))

class Cargo(TypeHandler):
    def _get_location_from_cargo_msg(self, message: dict) -> Optional[CargoLocation]:
        spans = message.get("spans")
        if spans is None or len(spans) < 1:
            return None
        span = spans[0]
        line = span.get("line_start")
        file = span.get("file_name")
        if line is not None and file is not None:
            return CargoLocation(file=file, line=line)
        return None

    def _parse_cargo_output(self, cargo_stdout: str, cargo_stderr: str) -> CargoOutput:
        """
        Parses the output of `cargo --message-format json`.
        """
        stdout_human = ""
        stderr_human = ""
        comments = [] 
        artifacts = []

        for line in cargo_stdout.splitlines():
            try:
                msg = json.loads(line)
                reason = msg.get("reason")
                if reason == "compiler-message":
                    m_content = msg.get("message", {})
                    rendered = m_content.get("rendered")
                    if rendered:
                        stderr_human += rendered
                    
                    location = self._get_location_from_cargo_msg(m_content)
                    text = m_content.get("message")
                    code_obj = m_content.get("code")
                    if code_obj and isinstance(code_obj, dict):
                         code_val = code_obj.get("code")
                         if code_val:
                             text += f" ({code_val})"
                    
                    if location and text:
                        comments.append(Comment(file=location.file, line=location.line, text=text, source="cargo"))

                elif reason == "compiler-artifact":
                    target = msg.get("target", {})
                    kind = target.get("kind", [])
                    name = target.get("name")
                    executable = msg.get("executable")
                    # We check for 'bin' kind and executable path
                    if "bin" in kind and executable and name:
                         artifacts.append(BinaryArtifact(name=name, path=executable))
            except json.JSONDecodeError:
                stdout_human += line + "\n"

        if cargo_stderr:
            stderr_human = f"{stderr_human.strip()}\n{cargo_stderr.strip()}"

        return CargoOutput(
            stdout=stdout_human.strip(),
            stderr=stderr_human,
            binary_artifacts=artifacts,
            comments=comments
        )

    def compile(self, container_image: str) -> CompileResult:
        cmd_type = self.config.get("cmd", "build")
        args = self.config.get("args", [])
        is_lib = self.config.get("lib", False)
        
        if isinstance(args, str):
            args = shlex.split(args)
            
        # 1. Synthesize Cargo.toml if missing
        local_files = os.listdir(self.evaluation.submit_path)
        if "Cargo.toml" not in local_files:
            rs_files = [f for f in local_files if f.endswith(".rs")]
            if len(rs_files) != 1:
                return BuildResult(False, "<div style='color: red'>No `Cargo.toml` found. Upload a crate or a single .rs file.</div>")
            
            # Synthesize a Cargo project
            manifest_content = f"""
[package]
name = "submit"
version = "0.1.0"
edition = "2024"
"""
            if is_lib:
                manifest_content += f"""
[lib]
path = "{rs_files[0]}"
"""
            else:
                manifest_content += f"""
[[bin]]
name = "main"
path = "{rs_files[0]}"
"""

            with open(os.path.join(self.evaluation.submit_path, "Cargo.toml"), "w") as f:
                f.write(manifest_content)

        # 2. Run Cargo with JSON output
        cargo_cmd = ["cargo", cmd_type, "--message-format", "json"]
        cargo_cmd.extend(args)
        
        env = {
            "RUST_BACKTRACE": "1",
            "CARGO_HOME": "/tmp/cargo",
            "CARGO_INCREMENTAL": "0",
            "CARGO_PROFILE_DEV_DEBUG": "line-tables-only",
        }

        res = self._run_docker_command(container_image, cargo_cmd, env)
        
        # 3. Parse Output
        parsed_output = self._parse_cargo_output(res.stdout, res.stderr)
        
        # 4. Handle Artifacts (Battle-tested logic from entry.py)
        if res.returncode != 0:
             public_cmd = ["cargo", cmd_type] + args
             parsed_output.stdout = f"`{' '.join(public_cmd)}` has exited with code {res.returncode}\n{parsed_output.stdout}"

        if len(parsed_output.binary_artifacts) > 1:
            names = ", ".join([a.name for a in parsed_output.binary_artifacts])
            parsed_output.stdout += f"\nWarning: multiple binary artifacts built ({names}).\nUsing the first one for further commands.\n"
            
        if len(parsed_output.binary_artifacts) > 0:
            # Artifact path is inside container: /work/target/...
            # We need to link it on host.
            artifact_rel = os.path.relpath(parsed_output.binary_artifacts[0].path, "/work")
            artifact_host = os.path.join(self.evaluation.submit_path, artifact_rel)
            
            main_link = os.path.join(self.evaluation.submit_path, "main")
            if os.path.isfile(main_link):
                os.unlink(main_link)
            
            # Verify file exists on host before linking
            if os.path.exists(artifact_host):
                os.symlink(artifact_host, main_link)

        # 5. Format HTML
        if not parsed_output.stdout:
            parsed_output.stdout = "Cargo finished successfully"
            
        html_out = f"<code style='filter: opacity(.7);'>$ {' '.join(cargo_cmd)}</code>"
        
        # Bleach and Format
        if parsed_output.stderr:
            safe_err = self._sanitize(parsed_output.stderr)
            if res.returncode == 0:
                html_out += f"<details><summary>Stderr</summary><pre><code>{safe_err}</code></pre></details>"
            else:
                 html_out += f"<pre><code>{safe_err}</code></pre>"
        
        html_out += f"<pre><code>{self._sanitize(parsed_output.stdout)}</code></pre>"

        if res.returncode == 0:
            html_out += "<div style='color: green'>Compilation succeeded</div>"
        else:
            html_out += f"<div style='color: red'>Exit code {res.returncode}</div>"

        # No need to convert to dict anymore, BuildResult handles it
        return BuildResult(res.returncode == 0, html_out, comments=parsed_output.comments)

class Dotnet(TypeHandler):
    def compile(self, container_image: str) -> BuildResult:
        run_tests = self.config.get("unittests", False)
        cwd = self.evaluation.submit_path
        
        proj_res = self._find_project_file(cwd)
        if proj_res.error:
            return BuildResult.fail(f"<span style='color:red'>{proj_res.error}</span>")

        build_command = self._build_command(run_tests, proj_res.path)
        
        res = self._run_docker_command(container_image, build_command.cmd, build_command.env)
        
        # Handle Artifacts
        if not run_tests and res.returncode == 0:
            exe_names = self._find_executable_projects(cwd)
            err = self._link_main_executable(cwd, build_command.output_dir, exe_names)
            if err:
                return BuildResult.fail(f"<span style='color:red'>{err}</span>")

        parse_res = self._parse_output(res.stdout, run_tests, cwd)
        
        html_out = self._format_html(build_command.cmd, res.stdout, res.returncode)

        return BuildResult(res.returncode == 0, html_out, comments=parse_res.comments, tests=parse_res.tests)

    def _find_project_file(self, cwd: str) -> ProjectFileResult:
        paths = os.listdir(cwd)
        sln = [p for p in paths if p.endswith(".sln")]
        csproj = [p for p in paths if p.endswith(".csproj")]
        nested_sln_path = None
        
        if not sln and not csproj:
             for root, dirs, files in os.walk(cwd):
                for f in files:
                    if f.endswith(".sln"):
                        nested_sln_path = os.path.relpath(os.path.join(root, f), cwd)
                        break
                if nested_sln_path:
                    break
             if not nested_sln_path:
                 return ProjectFileResult(error="No .sln or .csproj file was found in the root directory.")
        
        if len(sln) > 1:
            return ProjectFileResult(error="Multiple .sln files were found")
        if len(csproj) > 1:
             return ProjectFileResult(error="Multiple .csproj files were found")
             
        return ProjectFileResult(path=nested_sln_path)

    def _build_command(self, run_tests: bool, nested_sln_path: Optional[str]) -> BuildCommand:
        output_dir = "kelvin_output"
        cmd = ["dotnet"]
        if run_tests:
            cmd += ["test"]
            if nested_sln_path:
                cmd += ['"' + nested_sln_path + '"']
            cmd += ["-l", "trx;LogFileName=../../tests.xml"] 
        else:
            cmd += ["publish"]
            if nested_sln_path:
                cmd += ['"' + nested_sln_path + '"']
            cmd += ["--use-current-runtime", "--self-contained", "-o", output_dir]

        env = {
            "DOTNET_CLI_HOME": "/tmp/dotnet-cli-home",
            "XDG_DATA_HOME": "/tmp/dotnet-cli-home", # workaround for https://github.com/dotnet/core/issues/7868
            "DOTNET_NOLOGO": "1", # workaround for https://github.com/dotnet/sdk/issues/31457
            "DOTNET_EnableWriteXorExecute": "0",
        }
        return BuildCommand(cmd, env, output_dir)

    def _find_executable_projects(self, cwd: str) -> list[str]:
        """
        Scans for .csproj files in the directory to find projects with OutputType=Exe.
        Returns a list of project names (without extension).
        """
        import xml.etree.ElementTree as ET
        exe_names = []
        for proj_path in glob.glob(f"{cwd}/**/*.csproj", recursive=True):
                try:
                    tree = ET.parse(proj_path)
                    root = tree.getroot()
                    output_type = root.findtext("PropertyGroup/OutputType")
                    if output_type == "Exe":
                            exe_names.append(Path(proj_path).stem)
                except Exception:
                    pass
        return exe_names

    def _link_main_executable(self, cwd: str, output_dir: str, exe_names: list[str]) -> Optional[str]:
        """
        Finds the built executable in the output directory and symlinks it to 'main'.
        Returns an error string if multiple or zero executables are found, or None on success.
        """
        binaries = [Path(cwd) / output_dir / name for name in exe_names]
        valid_binaries = [b for b in binaries if b.exists()]
        
        if len(valid_binaries) == 1:
            target = valid_binaries[0]
            main_link = os.path.join(cwd, "main")
            if os.path.exists(main_link):
                os.unlink(main_link)
            os.symlink(target, main_link)
            return None
        elif len(valid_binaries) > 1:
                return f"Multiple executable projects found ({','.join(exe_names)}). Only upload one executable project."
        return None

    def _parse_output(self, stdout: str, run_tests: bool, cwd: str) -> ParseOutputResult:
        comments = []
        tests = []
        
        comment_re = re.compile(r"^/work/(?P<path>[^(]+)\((?P<line>[0-9]+),[0-9]+\): [^ ]+ (?P<source>[^ :])+:\s*(?P<text>.*?)\s\[.*?\]$")
        
        for line in stdout.splitlines():
                match = comment_re.match(line)
                if match:
                    item = match.groupdict()
                    comments.append(Comment(
                        file=item["path"],
                        line=int(item["line"]),
                        text=item["text"],
                        source=item["source"]
                    ))
                    
        if run_tests:
            tests_xml_path = os.path.join(cwd, "tests.xml")
            if os.path.exists(tests_xml_path):
                    import xml.etree.ElementTree as ET
                    ns = {"ns": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
                    try:
                        tree = ET.parse(tests_xml_path)
                        for node in tree.findall("ns:Results/ns:UnitTestResult", namespaces=ns):
                            text = []
                            for sel in ["./ns:Output/ns:ErrorInfo/ns:Message", "./ns:Output/ns:ErrorInfo/ns:StackTrace"]:
                                el = node.find(sel, namespaces=ns)
                                if el is not None and el.text:
                                    text.append(el.text)
                            
                            is_passed = node.attrib.get("outcome") == "Passed"
                            tests.append({
                                "name": node.attrib.get("testName"),
                                "success": is_passed,
                                "message": "\n".join(text).strip()
                            })
                        os.unlink(tests_xml_path)
                    except FileNotFoundError:
                        pass
        return ParseOutputResult(comments, tests)

    def _format_html(self, cmd: list[str], stdout: str, returncode: int) -> str:
        html_out = f"<code style='filter: opacity(.7);'>$ {' '.join(cmd)}</code>"
        html_out += f"<pre>{bleach.clean(stdout).replace(chr(10), '<br />')}</pre>"
        
        if returncode == 0:
                html_out += "<div style='color: green'>Build successful</div>"
        else:
                html_out += "<div style='color: red'>Build failed</div>"
        return html_out


class Java(TypeHandler):
    def compile(self, container_image: str) -> BuildResult:
        run_tests = self.config.get("unittests", False)
        cwd = self.evaluation.submit_path
        
        build_cmd = self._build_command(run_tests)
        
        res = self._run_docker_command(container_image, build_cmd.cmd)
        
        # 3. Handle Artifacts
        if not run_tests and res.returncode == 0:
            exec_classes = self._get_executable_class_names(cwd)
            if len(exec_classes) == 1:
                self._create_main_script(cwd, exec_classes[0])
            elif len(exec_classes) > 1:
                 return BuildResult(False, f"<span style='color:red'>Multiple executable classes found ({','.join(exec_classes)}). Only upload one executable class.</span>")

        # 4. Parse Comments & Tests
        parse_res = self._parse_output(res.stdout, run_tests, cwd)

        # 5. HTML Output
        html_out = self._format_html(build_cmd.cmd, res.stdout, res.returncode)

        return BuildResult(res.returncode == 0, html_out, comments=parse_res.comments, tests=parse_res.tests)

    def _build_command(self, run_tests: bool) -> BuildCommand:
        cmd = ["mvn", "--no-transfer-progress", "clean"]
        if run_tests:
            cmd += ["test", "-Dmaven.test.failure.ignore=true"]
        else:
            cmd += ["compile"]
            
        cmd += [
            "-Dmaven.compiler.showWarnings=true",
            "-Dmaven.compiler.showDeprecation=true",
            "-Dmaven.compiler.args=-Xlint:all",
        ]
        return BuildCommand(cmd, {}, "")

    def _get_executable_class_names(self, cwd: str) -> list[str]:
        src_path = os.path.join(cwd, "src", "main", "java")
        if not os.path.exists(src_path):
             return []

        def find_java_files(directory):
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith(".java"):
                        yield os.path.join(root, file)

        def is_executable_java_file(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                # Pattern to find main method in Java file
                pattern = re.compile(r"public\s+static\s+void\s+main\s*\(\s*String\s*\[\]\s+args\s*\)")
                return bool(re.search(pattern, content))

        def get_qualified_class_name(file_path, base_directory):
            # Remove .java extension and get relative path
            relative_path_without_extension = os.path.relpath(file_path, base_directory)[:-5]
            # Replace path separators with dots
            return relative_path_without_extension.replace(os.path.sep, ".")

        executable_classes = []
        for java_file in find_java_files(src_path):
            if is_executable_java_file(java_file):
                executable_classes.append(get_qualified_class_name(java_file, src_path))
        return executable_classes

    def _create_main_script(self, cwd: str, main_class: str):
        main_script_content = f"#!/bin/bash\nmvn --quiet exec:java -Dexec.mainClass={main_class}"
        main_script_path = os.path.join(cwd, "main")
        with open(main_script_path, "w") as f:
            f.write(main_script_content)
        os.chmod(main_script_path, 0o755)

    def _parse_output(self, stdout: str, run_tests: bool, cwd: str) -> ParseOutputResult:
        # parse compiler warnings / errors and add them as comments to the code
        comments = []
        # [WARNING] /work/src/main/java/kelvin/test_java/Application.java:[9,21] checkAccess() in java.lang.Thread has been deprecated and marked for removal
        # [ERROR] /work/src/main/java/kelvin/test_java/Application.java:[10,9] not a statement
        comment_re = re.compile(r"^\[(?P<source>ERROR|WARNING)\] (?P<path>.*?):\[(?P<line>[0-9]+),(?P<column>[0-9]+)\] (?P<text>.+)$")
        
        for line in stdout.splitlines():
             match = comment_re.match(line)
             if match:
                 item = match.groupdict()
                 comments.append(Comment(
                    file=item["path"],
                    line=int(item["line"]),
                    text=item["text"],
                    source=item["source"]
                 ))

        # Tests parsing
        tests = []
        if run_tests:
            tests = self._parse_tests_report(cwd)
            
        return ParseOutputResult(comments, tests)

    def _parse_tests_report(self, cwd: str) -> list[dict]:
        tests = []
        reports_path = os.path.join(cwd, "target", "surefire-reports")
        if os.path.exists(reports_path):
             import xml.etree.ElementTree as ET
             for p in glob.glob(os.path.join(reports_path, "*.xml")):
                 try:
                     tree = ET.parse(p)
                     for testcase in tree.findall(".//testcase"):
                         start_success = True
                         message = ""
                         failure = testcase.find("./failure")
                         error = testcase.find("./error")
                         sysout = testcase.find("./system-out")
                         
                         if failure is not None:
                             start_success = False
                             message = "Test FAILURE:\n" + failure.get("message", "") + "\n" + (failure.text or "").strip()
                         if error is not None:
                             start_success = False
                             message = "Test ERROR:\n" + error.get("message", "") + "\n" + (error.text or "").strip()
                         if sysout is not None:
                             message = message + "\n\n" + (sysout.text or "").strip()
                         
                         tests.append({
                             "name": testcase.get("name"),
                             "success": start_success,
                             "message": message.strip()
                         })
                     os.unlink(p)
                 except FileNotFoundError:
                     pass
        return tests

    def _format_html(self, cmd: list[str], stdout: str, returncode: int) -> str:
        html_out = f"<code>$ {' '.join(cmd)}</code>"
        safe_out = bleach.clean(stdout.strip())
        
        if returncode == 0:
             html_out += f"<details><summary>Stdout</summary><pre><code>{safe_out}</code></pre></details>"
             html_out += "<div style='color: green'>Build successful</div>"
        else:
             html_out += f"<pre><code>{safe_out}</code></pre>"
             html_out += "<div style='color: red'>Build failed</div>"
        return html_out


class Flake8(TypeHandler):
    def compile(self, container_image: str) -> BuildResult:
        cwd = self.evaluation.submit_path
        
        cmd = self._build_command()
        
        res = self._run_docker_command(container_image, cmd, {})
        
        comments = self._parse_output(res.stdout)
        
        html_out = self._format_html(cmd, res.stdout, res.returncode)

        return BuildResult(True, html_out, comments=comments)

    def _add_list_arg(self, name: str) -> list[str]:
        items = self.config.get(name)
        if items:
            try:
                # config is already parsed from yaml/json, so it might be list or string
                if isinstance(items, list):
                    items = ",".join(items)
                return [f"--{name}", items]
            except json.decoder.JSONDecodeError:
                pass
        return []

    def _build_command(self) -> list[str]:
        return [
            "flake8",
            "--format=%(path)s:%(row)d:%(code)s:%(text)s",
            *self._add_list_arg("select"),
            *self._add_list_arg("ignore"),
        ]

    def _parse_output(self, stdout: str) -> list[Comment]:
        # (file, line) -> [text]
        lint_results = defaultdict(list)
        
        for line in stdout.splitlines():
            try:
                parts = line.strip().split(":", 3)
                if len(parts) == 4:
                    path, line_num, code, text = parts
                    path = os.path.normpath(path)
                    lint_results[(path, int(line_num))].append(f"{text} [{code}]")
            except ValueError:
                pass

        comments = []
        for (file, line), texts in lint_results.items():
            comments.append(Comment(
                file=file,
                line=line,
                text=", ".join(texts),
                source="flake8"
            ))
        return comments

    def _format_html(self, cmd: list[str], stdout: str, returncode: int) -> str:
        html_out = f"<code>$ {' '.join(cmd)}</code>"
        safe_out = bleach.clean(stdout.strip())
        html_out += f"<pre><code>{safe_out}</code></pre>"
        
        if returncode == 0:
             html_out += "<div style='color: green'>Analysis finished (return code 0)</div>"
        else:
             html_out += f"<div style='color: orange'>Analysis finished with issues (exit code {returncode})</div>"
        return html_out


class ClangTidy(TypeHandler):
    def compile(self, container_image: str) -> BuildResult:
        cwd = self.evaluation.submit_path
        
        # 1. Find files
        files = self._find_files(cwd)
        if not files:
             return BuildResult(True, "No files found to analyze.")

        # 2. Build Command
        cmd = self._build_command(files)
        
        # 3. Run command
        res = self._run_docker_command(container_image, cmd, {})
        
        # 4. Load URLs
        urls = self._load_urls(container_image)

        # 5. Parse Comments
        comments = self._parse_output(res.stdout, urls)
        
        # 6. HTML Output
        html_out = self._format_html(cmd, res.stdout, res.returncode)
        
        return BuildResult(True, html_out, comments=comments)

    def _load_urls(self, container_image: str) -> dict[str, str]:
        urls = {}
        try:
            # Attempt to read /urls.json from the container
            res = self._run_docker_command(container_image, ["cat", "/urls.json"], {})
            if res.returncode == 0:
                urls = json.loads(res.stdout)
        except Exception:
            pass
        return urls

    def _find_files(self, cwd: str) -> list[str]:
        # config files or *.c, *.cpp, *.h, *.hpp
        files = []
        if self.config.get("files"):
             try:
                 files = self.config["files"]
             except: pass
        if not files:
            extensions = {".c", ".cpp", ".h", ".hpp"}
            for root, dirs, fnames in os.walk(cwd):
                for f in fnames:
                    if Path(f).suffix in extensions:
                        files.append(os.path.relpath(os.path.join(root, f), cwd))
        return files

    def _build_command(self, files: list[str]) -> list[str]:
        checks_arg = "*" # Default
        if self.config.get("checks") is not None:
            checks = self.config.get("checks")
            if isinstance(checks, list): checks = ",".join(checks)
            checks_arg = checks
        else:
             # Match legacy default checks
             checks = [
                "*",
                "-cppcoreguidelines-avoid-magic-numbers",
                "-readability-magic-numbers",
                "-cert-*",
                "-llvm-include-order",
                "-cppcoreguidelines-init-variables",
                "-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling",
                "-bugprone-narrowing-conversions",
                "-cppcoreguidelines-narrowing-conversions",
                "-android-cloexec-fopen",
                "-readability-braces-around-statements",
                "-google-readability-todo",
             ]
             checks_arg = ",".join(checks)

        return [
            "clang-tidy",
            "-extra-arg=-std=c++17",
            f"--checks={checks_arg}",
            *files
        ]

    def _parse_output(self, stdout: str, urls: dict[str, str]) -> list[Comment]:
        comments = []
        # Regex for standard clang output: path:line:col: severity: message [check-name]
        # Example: /work/main.c:10:5: warning: message [check-name]
        regex = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<severity>[^:]+):\s*(?P<text>.*)$")
        check_name_regex = re.compile(r"\[([^\]]+)\]$")

        for line in stdout.splitlines():
            line = line.strip()
            match = regex.match(line)
            if match:
                item = match.groupdict()
                path = item["path"]
                # Strip /work/ prefix if present
                if path.startswith("/work/"):
                    path = path[6:]
                
                text = item['text']
                url = None
                
                # Extract check name from text
                check_match = check_name_regex.search(text)
                if check_match:
                    check_name = check_match.group(1)
                    url = urls.get(check_name)
                
                comments.append(Comment(
                    file=path,
                    line=int(item["line"]),
                    text=f"{text} ({item['severity']})",
                    source="clang-tidy",
                    url=url
                ))
        return comments

    def _format_html(self, cmd: list[str], stdout: str, returncode: int) -> str:
        html_out = f"<code>$ {' '.join(cmd)}</code>"
        safe_out = bleach.clean(stdout.strip())
        
        if returncode == 0:
             html_out += f"<details><summary>Output</summary><pre><code>{safe_out}</code></pre></details>"
             html_out += "<div style='color: green'>Analysis finished (return code 0)</div>"
        else:
             html_out += f"<pre><code>{safe_out}</code></pre>"
             html_out += f"<div style='color: orange'>Analysis finished with issues (exit code {returncode})</div>"
        return html_out
