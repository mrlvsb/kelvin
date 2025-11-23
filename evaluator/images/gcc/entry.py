#!/usr/bin/python3
import html
import io
import json
import subprocess
import os
import shlex


SANITIZED_FILES = ["result.html", "piperesult.json"]

output = os.getenv("PIPE_OUTPUT", "main")
flags = os.getenv("PIPE_FLAGS", "")
ldflags = os.getenv("PIPE_LDFLAGS", "")
cmakeflags = os.getenv("PIPE_CMAKEFLAGS", "[]")
makeflags = os.getenv("PIPE_MAKEFLAGS", "[]")


# TODO: replace with shlex.join on python3.8
def shlex_join(split_command):
    return " ".join(shlex.quote(arg) for arg in split_command)


def cmd_run(cmd, out, show_cmd=None, env=None):
    if not show_cmd:
        show_cmd = cmd

    if env:
        env = {**os.environ, **env}

    out.write(f"<code style='filter: opacity(.7);'>$ {shlex_join(show_cmd)}</code>")

    with open("/tmp/out", "w+", errors="ignore") as gcc_out:
        p = subprocess.Popen(cmd, stdout=gcc_out, stderr=gcc_out, env=env)
        p.wait()

        gcc_out.seek(0)
        out.write(f"<kelvin-terminal-output>{html.escape(gcc_out.read())}</kelvin-terminal-output>")
        return p.returncode


class CompilationException(BaseException):
    pass


def compile(makeflags: str, cmakeflags: str, html_output: io.StringIO):
    env = {
        "CC": "gcc",
        "CXX": "g++",
        "CFLAGS": flags,
        "CXXFLAGS": flags,
        "LDFLAGS": ldflags,
        "CLICOLOR_FORCE": "1",
        "PATH": f'/wrapper:{os.getenv("PATH")}',
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
    }

    if "cmakelists.txt" in [f.lower() for f in os.listdir(".")]:
        cmakeflags = json.loads(cmakeflags)
        cmake_exitcode = cmd_run(["cmake", *cmakeflags, "."], html_output, env=env)
        if cmake_exitcode != 0:
            raise CompilationException(f"Could not run CMake, exit code {cmake_exitcode}")

    # The file list needs to be queried again
    if "makefile" in [f.lower() for f in os.listdir(".")]:
        makeflags = json.loads(makeflags)
        make_exitcode = cmd_run(["make", *makeflags], html_output, env=env)
        if make_exitcode != 0:
            raise CompilationException(f"Could not run Make, exit code {make_exitcode}")
    else:
        sources = []
        for root, dirs, files in os.walk("."):
            for f in files:
                if f.split(".")[-1] in ["c", "cpp"]:
                    sources.append(os.path.join(root, f))

        if not sources:
            raise CompilationException(
                "Missing source files! please upload .c or .cpp files!</div>"
            )

        use_cpp = any(f.endswith(".cpp") for f in sources)
        compile_cmd = [
            "g++" if use_cpp else "gcc",
            *sources,
            "-o",
            output,
            *shlex.split(flags),
            *shlex.split(ldflags),
        ]
        gcc_exitcode = cmd_run(compile_cmd, html_output, show_cmd=compile_cmd, env=env)

        if gcc_exitcode == 0:
            out.write("<div style='color: green'>Compilation succeeded</div>")
        else:
            raise CompilationException(f"Failed to run GCC, exit code {gcc_exitcode}")

    if output and not os.path.exists(output):
        executables = [f for f in os.listdir() if os.access(f, os.X_OK) and not os.path.isdir(f)]
        if len(executables) == 0:
            raise CompilationException("No executable has been built.")
        elif len(executables) > 1:
            raise CompilationException(
                f"Multiple executables have been built: {','.join(executables)}"
            )

        html_output.write(
            f"<code style='filter: opacity(.7);'>$ mv {executables[0]} {output}</code>"
        )
        os.rename(executables[0], output)


result_file = "result.html"

html_output = io.StringIO()
returncode = 1

try:
    compile(makeflags, cmakeflags, html_output)
    returncode = 0
except BaseException as e:
    if isinstance(e, CompilationException):
        html_output.write(f"<div style='color: red'>{str(e)}</div>")
finally:
    for file in SANITIZED_FILES:
        try:
            # Make sure that no sanitized file was written
            os.unlink(file)
        except:  # noqa
            pass

with open("result.html", "w") as out:
    out.write(html_output.getvalue())

exit(returncode)
