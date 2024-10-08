#!/usr/bin/env python3
import os
import subprocess
from collections import defaultdict
from pathlib import Path

import yaml
import json


class OffsetToLine:
    def __init__(self, root):
        self.root = root
        self.files = {}

    def to_line(self, path, offset):
        if path not in self.files:
            self.files[path] = self.build(path)

        for line, threshold in enumerate(self.files[path]):
            if threshold > offset:
                return line + 1
        return len(self.files[path])

    def build(self, path):
        offsets = []
        with open(os.path.join(self.root, path), "rb") as f:
            for offset, byte in enumerate(f.read()):
                if byte == ord("\n"):
                    offsets.append(offset)
        return offsets


s = os.environ.get("PIPE_CHECKS", "")
if s:
    checks = json.loads(s)
else:
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

files = os.environ.get("PIPE_FILES", "")
if files:
    files = json.loads(files)
else:
    extensions = [".c", ".cpp", ".h", ".hpp"]
    files = [str(p.resolve()) for p in Path(os.getcwd()).glob("./**/*") if p.suffix in extensions]

cmd = [
    "clang-tidy",
    "-extra-arg=-std=c++17",
    "--export-fixes=/tmp/fixes.yaml",
    f"--checks={','.join(checks)}",
    *files,
]

print(cmd)
subprocess.Popen(cmd).wait()

urls = {}
with open("/urls.json") as f:
    urls = json.load(f)

offset_to_line = OffsetToLine("")
comments = defaultdict(list)
try:
    with open("/tmp/fixes.yaml") as f:
        for err in yaml.load(f.read(), Loader=yaml.SafeLoader)["Diagnostics"]:
            seen = set()

            for note in [
                err,
                err["DiagnosticMessage"] if "DiagnosticMessage" in err else {},
            ]:  # , *err['Notes']]:
                if "Message" not in note or note["Message"] in seen:
                    continue
                seen.add(note["Message"])
                source = os.path.basename(note["FilePath"])
                comments[source].append(
                    {
                        "line": offset_to_line.to_line(source, note["FileOffset"]),
                        "text": note["Message"],
                        "source": err["DiagnosticName"],
                        "url": urls.get(err["DiagnosticName"], None),
                    }
                )

    with open("piperesult.json", "w") as out:
        json.dump({"comments": comments}, out, indent=4, sort_keys=True)
except FileNotFoundError:
    # no errors or warnings generated by clang-tidy
    pass
