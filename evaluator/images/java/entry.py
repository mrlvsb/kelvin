#!/usr/bin/python3
import dataclasses
import os
import subprocess
import json
import re
import glob
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import bleach


@dataclasses.dataclass
class BuildResult:
    success: bool
    output: str
    comments: Optional[Dict[str, List[str]]] = dataclasses.field(default_factory=dict)
    tests: Optional[List[dict]] = dataclasses.field(default_factory=list)

    @staticmethod
    def fail(error: str) -> "BuildResult":
        return BuildResult(
            success=False,
            output=error,
        )


def parse_tests_report(path):
    try:
        tests = []
        for path in glob.glob(os.path.join(path, "*.xml")):
            tree = ET.parse(path)
            os.unlink(path)

            for testcase in tree.findall('.//testcase'):
                success = True
                message = ""
                failure = testcase.find('./failure')
                
                if failure is not None:
                    success = False
                    message = failure.get('message', '') + "\n" + (failure.text or '').strip()
                    
                tests.append({
                    'name': testcase.get('name'),
                    'success': success,
                    'message': message.strip(),
                })

        return tests
    except FileNotFoundError:
        return []


def get_executable_class_names(directory: Path) -> List[str]:
    def find_java_files(directory):
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".java"):
                    yield os.path.join(root, file)

    def is_executable_java_file(file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            # Vzor pro nalezení metody main v Java souboru
            pattern = re.compile(r"public\s+static\s+void\s+main\s*\(\s*String\s*\[\]\s+args\s*\)")
            return bool(re.search(pattern, content))

    def get_qualified_class_name(file_path, base_directory):
        # Odstranění přípony .java a získání relativní cesty
        relative_path_without_extension = os.path.relpath(file_path, base_directory)[:-5]
        # Nahrazení oddělovačů cesty tečkami
        return relative_path_without_extension.replace(os.path.sep, '.')
    
    executable_classes = []
    for java_file in find_java_files(directory):
        if is_executable_java_file(java_file):
            executable_classes.append(get_qualified_class_name(java_file, directory))
    return executable_classes


def build_java_project(run_tests: bool) -> BuildResult:
    # build or build+run tests
    tests_path = "target/surefire-reports"
    env = os.environ.copy()
    cmd = ['mvn', 'clean']
    if run_tests:
        cmd += ['test', '-Dmaven.test.failure.ignore=true']
    else:
        cmd += ['compile']
    cmd += [ '-Dmaven.compiler.showWarnings=true', '-Dmaven.compiler.showDeprecation=true', '-Dmaven.compiler.args=-Xlint:all' ]
    process = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # find an executable file in the output directory and create a symlink for the following tasks
    # in the pipeline
    
    executable_class_names = get_executable_class_names(Path(os.getcwd() + "/src/main/java"))
    
    if len(executable_class_names) == 1:
        main_script_lines = [ 
           "#!/bin/bash",
           f"JAVA_HOME={os.environ['JAVA_HOME']}",
           f"MAVEN_HOME={os.environ['MAVEN_HOME']}",
           f"M2_HOME={os.environ['M2_HOME']}",
           f"PATH={os.environ['PATH']}",
           f"mvn --quiet exec:java -Dexec.mainClass={executable_class_names[0]}"
        ]
        script_name = "main"
        with open(script_name, "w") as file:
            file.write("\n".join(main_script_lines))
        subprocess.run(["chmod", "+x", script_name])

    elif len(executable_class_names) > 1:
        return BuildResult.fail(
            f"Multiple executable classes found ({','.join(executable_class_names)}). "
            f"Only upload one executable class."
        )
    
    # parse compiler warnings / errors and add them as comments to the code
    comments = defaultdict(list)
    #[WARNING] /work/src/main/java/kelvin/test_java/Application.java:[9,21] checkAccess() in java.lang.Thread has been deprecated and marked for removal
    #"[ERROR] /work/src/main/java/kelvin/test_java/Application.java:[10,9] not a statement
    pattern = re.compile(r'^\[(?P<source>ERROR|WARNING)\] (?P<path>.*?):\[(?P<line>[0-9]+),(?P<column>[0-9]+)\] (?P<text>.+)$')

    for line in process.stdout.decode().splitlines():
        match = re.match(pattern, line)        
        
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


def get_java_home():
    try:
        java_bin_path = subprocess.check_output("which java", shell=True, text=True).strip()
        java_real_path = subprocess.check_output(f"readlink -f {java_bin_path}", shell=True, text=True).strip()
        java_home = os.path.dirname(os.path.dirname(java_real_path))
        return java_home
    except subprocess.CalledProcessError:
        # Zde můžete logovat chybu nebo vrátit výchozí hodnotu
        return None
    
# set environment variables
os.environ['JAVA_HOME'] = get_java_home() or '/usr/lib/jvm/default-java'
os.environ['M2_HOME'] = '/opt/maven'
os.environ['MAVEN_HOME'] = '/opt/maven'
os.environ['PATH'] = f"{os.environ['M2_HOME']}/bin:{os.environ['PATH']}"

run_tests = os.getenv("PIPE_UNITTESTS", False)
result = build_java_project(run_tests)

with open("result.html", "w") as out:
    stdout = bleach.clean(result.output.strip()).replace("\n", "<br />")
    out.write(f'<pre>{stdout}</pre>')

with open('piperesult.json', 'w') as out:
    json.dump({"comments": result.comments, "tests": result.tests}, out, indent=4, sort_keys=True)


exit(not result.success)