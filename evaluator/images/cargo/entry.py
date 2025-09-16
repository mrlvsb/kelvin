#!/usr/bin/env python3

import dataclasses
import json
import os
import subprocess
from collections import defaultdict
from typing import Any, Dict, List, Tuple, TypedDict

import bleach

"""
This script invokes Cargo with the specified arguments, and turns the resulting diagnostics
into Kelvin comments. If a binary artifact is built, it copied it to a file called `main`
in the working directory of the pipeline.

Pipeline parameters:
`cmd` - string with the Cargo command that should be executed (e.g. `build` or `test`).
`args` - list of additional command line parameters for Cargo.
`lib` - whether to compile the project as a library, rather than a binary (default=false)
"""


class Comment(TypedDict):
    line: int
    text: str
    source: str


@dataclasses.dataclass
class BuildResult:
    success: bool
    stdout: str
    stderr: str
    comments: Dict[str, List[Comment]] = dataclasses.field(default_factory=dict)

    @staticmethod
    def fail(stdout: str, stderr="") -> "BuildResult":
        return BuildResult(success=False, stdout=stdout, stderr=stderr)


def get_param(name: str, default: Any, parse_json: bool = False) -> Any | None:
    value = os.getenv(f"PIPE_{name.upper()}")
    if value is None:
        return default
    if parse_json:
        return json.loads(value)
    return value


@dataclasses.dataclass
class BinaryArtifact:
    name: str
    path: str


@dataclasses.dataclass
class CargoOutput:
    stdout: str
    stderr: str
    comments: Dict[str, List[Comment]]
    binary_artifacts: List[BinaryArtifact]


# Returns (file, line)
def get_location_from_cargo_msg(message) -> Tuple[str, int] | None:
    spans = message.get("spans")
    if spans is None or len(spans) < 1:
        return None
    span = spans[0]
    line = span.get("line_start")
    file = span.get("file_name")
    if line is not None and file is not None:
        return (file, line)


def parse_cargo_output(cargo_stdout: str) -> CargoOutput:
    """
    Parses the output of `cargo --message-format json`.
    Reconstructs stdout/stderr and created Kelvin comments out of Cargo warnings.
    """
    stdout = ""
    stderr = ""
    comments: Dict[str, List[Comment]] = defaultdict(list)
    artifacts = []

    for line in cargo_stdout.splitlines(keepends=False):
        # JSON message
        if line.startswith("{"):
            message = json.loads(line)
            reason = message.get("reason")
            if reason == "compiler-message":
                msg = message.get("message", {})
                rendered = msg.get("rendered", None)
                # Add the rendered message to stderr, it would be normally printed there
                if rendered is not None:
                    stderr += f"{rendered}"
                location = get_location_from_cargo_msg(msg)
                text = msg.get("message")

                code = msg.get("code")
                if code is not None and isinstance(code, dict) and "code" in code:
                    code = code["code"]
                    text += f" ({code})"

                if location is not None and text is not None:
                    (file, line) = location
                    comments[file].append({"line": line, "text": text, "source": "cargo"})
            elif reason == "compiler-artifact":
                target = message.get("target", {})
                name = target.get("name")
                is_binary = "bin" in target.get("kind")
                executable = message.get("executable")
                if is_binary and executable is not None and name is not None:
                    artifacts.append(BinaryArtifact(name=name, path=executable))
        else:
            # Normal text message, add to stdout
            stdout += f"{line}\n"

    return CargoOutput(stdout=stdout, stderr=stderr, comments=comments, binary_artifacts=artifacts)


def run_cargo(command: str, args: List[str]) -> BuildResult:
    paths = os.listdir(os.getcwd())
    manifest_found = "Cargo.toml" in paths
    rs_files = [p for p in paths if p.endswith(".rs")]
    if not manifest_found:
        if len(rs_files) != 1:
            return BuildResult.fail(
                "No `Cargo.toml` found. Either upload a whole crate (`Cargo.toml` + `src`) or a single .rs file."
            )
        # Synthesize a Cargo project
        manifest = """
[package]
name = "submit"
version = "0.1.0"
edition = "2024"
"""
        lib_target = get_param("lib", default="False") == "True"
        if lib_target:
            manifest += f"""
[lib]
path = "{rs_files[0]}"
"""
        else:
            manifest += f"""
[[bin]]
name = "main"
path = "{rs_files[0]}"
"""

        with open("Cargo.toml", "w") as f:
            f.write(manifest)

    env = os.environ.copy()
    env.update(
        dict(
            # Make the build a bit faster, we don't need incremental build
            CARGO_INCREMENTAL="0",
            # Improve compilation time and reduce disk usage
            CARGO_PROFILE_DEV_DEBUG="line-tables-only",
        )
    )
    cmdline = ["cargo", command, "--message-format", "json", *args]
    result = subprocess.run(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout = result.stdout.decode()
    stderr = result.stderr.decode()

    output = parse_cargo_output(stdout)
    stdout = output.stdout.strip()
    stderr = f"{output.stderr.strip()}\n{stderr.strip()}"

    if result.returncode != 0:
        public_cmdline = ["cargo", command, *args]
        return BuildResult.fail(
            f"`{' '.join(public_cmdline)}` has exited with code {result.returncode}\n{stdout}",
            stderr=stderr,
        )

    artifacts = output.binary_artifacts
    if len(artifacts) > 1:
        stdout += f"""
Warning: multiple binary artifacts built ({', '.join([artifact.name for artifact in artifacts])}).
Using the first one for further commands.
"""
    if len(artifacts) > 0:
        if os.path.isfile("main"):
            os.remove("main")
        os.symlink(artifacts[0].path, "main")

    if not stdout:
        stdout = "Cargo finished successfully"
    return BuildResult(success=True, stdout=stdout, stderr=stderr, comments=output.comments)


COMMAND = get_param("cmd", "build")
ARGS = get_param("args", [], parse_json=True)

try:
    result = run_cargo(COMMAND, ARGS)
except BaseException as e:
    result = BuildResult.fail(f"Cargo execution failed\n{e}")

with open("result.html", "w") as out:
    stdout = bleach.clean(result.stdout.strip())
    if result.stderr.strip():
        stderr = bleach.clean(result.stderr.strip())
        stderr = f"<pre><code>{stderr}</code></pre>"
        if result.success:
            out.write(f"""<details>
<summary>Stderr</summary>

{stderr}

</details>
""")
        else:
            out.write(stderr)
    out.write(f"<pre><code>{stdout}</code></pre>")

with open("piperesult.json", "w") as out:
    json.dump({"comments": result.comments}, out, indent=4, sort_keys=True)

exit(not result.success)
