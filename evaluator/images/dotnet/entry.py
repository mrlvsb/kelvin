#!/usr/bin/python3
import dataclasses
import os
import subprocess
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Optional
import xml.etree.ElementTree as ET

import bleach


@dataclasses.dataclass
class BuildResult:
    success: bool
    error: Optional[str] = None
    output: Optional[str] = None
    comments: Optional[List[dict]] = dataclasses.field(default_factory=list)
    tests: Optional[List[dict]] = dataclasses.field(default_factory=list)

    @staticmethod
    def fail(error: str) -> "BuildResult":
        return BuildResult(
            success=False,
            error=error,
        )


def parse_tests_report(path):
    try:
        ns={'ns': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
        tree = ET.parse(path)
        os.unlink(path)

        tests = []
        for node in tree.findall('ns:Results/ns:UnitTestResult', namespaces=ns):
            text = []

            for sel in ['./ns:Output/ns:ErrorInfo/ns:Message', './ns:Output/ns:ErrorInfo/ns:StackTrace']:
                el = node.find(sel, namespaces=ns)
                if el is not None:
                    text.append(el.text)

            success = node.attrib['outcome'] == 'Passed'

            tests.append({
                'name': node.attrib['testName'],
                'success': success,
                'message': "\n".join(text).strip(),
            })

        return tests
    except FileNotFoundError:
        return []

def build_dotnet_project(run_tests: bool) -> BuildResult:
    paths = os.listdir(os.getcwd())
    sln = [p for p in paths if Path(p).suffix == ".sln"]
    csproj = [p for p in paths if Path(p).suffix == ".csproj"]

    if sln and csproj:
        return BuildResult.fail("Both .sln and .csproj file was found.")
    if not sln and not csproj:
        return BuildResult.fail("No .sln or .csproj file was found")
    if len(sln) > 1:
        return BuildResult.fail("Multiple .sln files were found")
    if len(csproj) > 1:
        return BuildResult.fail("Multiple .csproj files were found")

    # build or build+run tests
    tests_path = "tests.xml"
    env = os.environ.copy()
    env["DOTNET_CLI_HOME"] = "/tmp/dotnet-cli-home"
    env["DOTNET_NOLOGO"] = "1"
    cmd = ['dotnet']
    if run_tests:
        cmd += ['test', '-l', f'trx;LogFileName=../../{tests_path}']
    else:
        cmd += ['publish', '--use-current-runtime', '--self-contained']
    process = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # find binary and create symlink for a following tasks in pipeline
    if csproj:
        for root, dirs, files in os.walk('bin/Debug/'):
            for file in files:
                full_path = os.path.join(root, file)
                if full_path.endswith(f'/linux-x64/publish/{Path(csproj[0]).stem}'):
                    os.symlink(full_path, "main")
    
        

    # parse compiler warnings / errors and add them as comments to the code
    comments = defaultdict(list)
    for line in process.stdout.decode().splitlines():
        # /work/Program.cs(82,32): warning CS8600: Converting null literal or possible null value to non-nullable type. [/work/Du1.csproj]
        match = re.match(r'^/work/(?P<path>[^(]+)\((?P<line>[0-9]+),[0-9]+\): [^ ]+ (?P<source>[^ :])+:\s*(?P<text>.*?)\s\[.*?\]$', line)
        if match:
            comment = match.groupdict()
            comments[comment['path']].append(comment)  

    tests = []
    if run_tests:
        tests = parse_tests_report(tests_path)

    return BuildResult(
        success=process.returncode == 0,
        output=process.stdout.decode(),
        comments=comments,
        tests=tests,
    )


run_tests = os.getenv("PIPE_TESTS", False)
result = build_dotnet_project(run_tests)

with open("result.html", "w") as out:
    stdout = bleach.clean(result.output.strip()).replace("\n", "<br />")
    out.write(f'<pre>{stdout}</pre>')

with open('piperesult.json', 'w') as out:
    json.dump({"comments": result.comments, "tests": result.tests}, out, indent=4, sort_keys=True)


exit(not result.success)