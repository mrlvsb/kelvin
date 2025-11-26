#!/usr/bin/python3
import dataclasses
import os
import subprocess
import json
import re
import glob
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
import xml.etree.ElementTree as ET

import bleach

SANITIZED_FILES = ["result.html", "piperesult.json"]


@dataclasses.dataclass
class BuildResult:
    success: bool
    output: str
    comments: Dict[str, List[str]] | None = dataclasses.field(default_factory=dict)
    tests: List[dict] | None = dataclasses.field(default_factory=list)

    @staticmethod
    def fail(error: str) -> "BuildResult":
        return BuildResult(
            success=False,
            output=error,
        )


def parse_tests_report(path):
    try:
        ns = {"ns": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        tree = ET.parse(path)
        os.unlink(path)

        tests = []
        for node in tree.findall("ns:Results/ns:UnitTestResult", namespaces=ns):
            text = []

            for sel in [
                "./ns:Output/ns:ErrorInfo/ns:Message",
                "./ns:Output/ns:ErrorInfo/ns:StackTrace",
            ]:
                el = node.find(sel, namespaces=ns)
                if el is not None:
                    text.append(el.text)

            success = node.attrib["outcome"] == "Passed"

            tests.append(
                {
                    "name": node.attrib["testName"],
                    "success": success,
                    "message": "\n".join(text).strip(),
                }
            )

        return tests
    except FileNotFoundError:
        return []


def get_executable_project_names(directory: Path) -> List[str]:
    """
    Find all `.csproj` files in the given directory and return the names of the found
    projects that should produce an executable output.
    """
    import xml.etree.ElementTree as ET

    names = []
    for proj_path in glob.glob(f"{directory}/**/*.csproj", recursive=True):
        try:
            tree = ET.parse(proj_path)
            root = tree.getroot()
            output_type = root.findtext("PropertyGroup/OutputType")
            if output_type == "Exe":
                name = Path(proj_path).stem
                names.append(name)
        except BaseException:
            pass
    return names


def find_nested_sln(path):
    for i in os.scandir(path):
        if i.is_file():
            if Path(i.path).suffix == ".sln":
                return i.path
        elif i.is_dir():
            tmp = find_nested_sln(i.path)
            if tmp is not None:
                return tmp
    return None


def build_dotnet_project(run_tests: bool) -> BuildResult:
    output_dir = "output"
    paths = os.listdir(os.getcwd())
    sln = [p for p in paths if Path(p).suffix == ".sln"]
    csproj = [p for p in paths if Path(p).suffix == ".csproj"]
    nested_sln_path = None

    if not sln and not csproj:
        nested_sln_path = find_nested_sln(os.getcwd())
        if nested_sln_path is None:
            return BuildResult.fail("No .sln or .csproj file was found in the root directory.")
    if len(sln) > 1:
        return BuildResult.fail("Multiple .sln files were found")
    if len(csproj) > 1:
        return BuildResult.fail("Multiple .csproj files were found")

    # build or build+run tests
    tests_path = "tests.xml"
    env = os.environ.copy()
    env["DOTNET_CLI_HOME"] = "/tmp/dotnet-cli-home"
    # workaround for https://github.com/dotnet/core/issues/7868
    env["XDG_DATA_HOME"] = "/tmp/dotnet-cli-home"
    env["DOTNET_NOLOGO"] = "1"
    # workaround for https://github.com/dotnet/sdk/issues/31457
    env["DOTNET_EnableWriteXorExecute"] = "0"
    cmd = ["dotnet"]
    if run_tests:
        cmd += ["test"]
        if nested_sln_path:
            cmd += ['"' + nested_sln_path + '"']
        cmd += ["-l", f"trx;LogFileName=../../{tests_path}"]
    else:
        cmd += ["publish"]
        if nested_sln_path:
            cmd += ['"' + nested_sln_path + '"']
        cmd += ["--use-current-runtime", "--self-contained", "-o", output_dir]
    process = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # find an executable file in the output directory and create a symlink for the following tasks
    # in the pipeline
    exe_project_names = get_executable_project_names(Path(os.getcwd()))
    binaries = [Path(output_dir) / name for name in exe_project_names]
    if len(binaries) == 1:
        os.symlink(binaries[0], "main")
    elif len(binaries) > 1:
        return BuildResult.fail(
            f"Multiple executable projects found ({','.join(exe_project_names)}). "
            f"Only upload one executable project."
        )

    # parse compiler warnings / errors and add them as comments to the code
    comments = defaultdict(list)
    for line in process.stdout.decode().splitlines():
        # /work/Program.cs(82,32): warning CS8600: Converting null literal or possible null value to non-nullable type. [/work/Du1.csproj]
        match = re.match(
            r"^/work/(?P<path>[^(]+)\((?P<line>[0-9]+),[0-9]+\): [^ ]+ (?P<source>[^ :])+:\s*(?P<text>.*?)\s\[.*?\]$",
            line,
        )
        if match:
            comment = match.groupdict()
            comments[comment["path"]].append(comment)

    tests = []
    if run_tests:
        tests = parse_tests_report(tests_path)

    return BuildResult(
        success=process.returncode == 0,
        output=process.stdout.decode(),
        comments=comments,
        tests=tests,
    )


run_tests = os.getenv("PIPE_UNITTESTS", False)
result = build_dotnet_project(run_tests)

for file in SANITIZED_FILES:
    try:
        # unlink any result files created by the student's build script
        os.unlink(file)
    except:
        pass


with open("result.html", "w") as out:
    stdout = bleach.clean(result.output.strip()).replace("\n", "<br />")
    out.write(f"<pre>{stdout}</pre>")

with open("piperesult.json", "w") as out:
    json.dump({"comments": result.comments, "tests": result.tests}, out, indent=4, sort_keys=True)


exit(not result.success)
