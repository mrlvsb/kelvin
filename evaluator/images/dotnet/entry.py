#!/usr/bin/python3

import dataclasses
import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import bleach


@dataclasses.dataclass
class BuildResult:
    success: bool
    stderr: Optional[str] = None
    stdout: Optional[str] = None
    binaries: Optional[List[Path]] = None

    @staticmethod
    def fail(stdout: str = "", stderr: str = "") -> "BuildResult":
        return BuildResult(
            success=False,
            stdout=stdout,
            stderr=stderr
        )


def build_dotnet_project(output_name: str) -> BuildResult:
    # Rename .csprof file to <output-name>.csproj
    paths = os.listdir(os.getcwd())
    sln = [p for p in paths if Path(p).suffix == ".sln"]
    #csproj = [p for p in paths if Path(p).suffix == ".csproj"]
    if not sln:
        return BuildResult.fail(stderr="No .sln file was found")
    elif len(sln) > 1:
        return BuildResult.fail(stderr="Multiple .sln files were found")
    else:
        sln = sln[0]
        os.rename(sln, f"{output_name}.sln")

    artifact_dir = "build"

    env = os.environ.copy()
    env["DOTNET_CLI_HOME"] = "/tmp/dotnet-cli-home"

    logging.info("Building dotnet project")

    # Build the .NET project
    result = subprocess.run([
        "dotnet",
        "test"
    ],
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE)
    if result.returncode != 0:
        return BuildResult(
            success=False,
            stderr=result.stderr.decode(),
            stdout=result.stdout.decode(),
        )

    # Try to find binary
    binaries = []
    '''
    binary_path = Path(artifact_dir) / output_name
    binaries = []
    if os.access(binary_path, os.X_OK):
        binaries.append(binary_path)
    '''
    return BuildResult(
        success=True,
        stderr=result.stderr.decode(),
        stdout=result.stdout.decode(),
        binaries=binaries
    )


output = os.getenv("PIPE_OUTPUT", "main")

result = build_dotnet_project(output_name=output)

with open("result.html", "w") as out:
    if not result.success:
        stdout = bleach.clean(result.stdout.strip()).replace("\n", "<br />")
        stderr = bleach.clean(result.stderr.strip()).replace("\n", "<br />")
        out.write("<span style='color: red'>Project was not compiled successfully!</span>")
        if stderr:
            out.write(f"<div>Stderr<br />{stderr}</div>")
        if stdout:
            out.write(f"<div>Stdout<br />{stdout}</div>")
        exit(1)
    else:
        stdout = bleach.clean(result.stdout.strip()).replace("\n", "<br />")
        stderr = bleach.clean(result.stderr.strip()).replace("\n", "<br />")
        out.write("<span style='color: red'>Project was not compiled successfully!</span>")
        if stderr:
            out.write(f"<div>Stderr<br />{stderr}</div>")
        if stdout:
            out.write(f"<div>Stdout<br />{stdout}</div>")
        exit(1)

    '''
    bins = result.binaries
    if len(bins) == 0:
        out.write("<span style='color: red'>No executable has been built.</span>")
        exit(1)
    elif len(bins) > 1:
        out.write(
            f"<span style='color: red'>Multiple executables have been built: "
            f"{','.join([bleach.clean(bin.name) for bin in bins])}</span>")
        exit(1)
    else:
        out.write("<div>Project was successfully built</div>")
        out.write(
            f"<code style='color: #444; font-weight: bold'>$ mv "
            f"{bleach.clean(str(bins[0]))} {output}</code>")
        os.rename(bins[0], output)
    '''
