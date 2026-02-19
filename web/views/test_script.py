import io
from pathlib import Path

from evaluator.evaluation import EvaluationContext

ASSETS_DIR = Path(__file__).absolute().parent / "assets"
SCRIPT_TEMPLATE = ASSETS_DIR / "run-tests.py"


def render_test_script(eval_ctx: EvaluationContext) -> io.BytesIO:
    """
    Renders the script at assets/run-tests.py, and passes information about tests to it.
    The script will then run all tests and check if they were executed correctly.
    """
    content = ""
    known_streams = ("stdout", "stderr", "stdin")
    for test in eval_ctx.tests:
        args = [str(arg) for arg in test.args]
        exit_code = test.exit_code
        name = test.name
        title = test.title

        stdin = "stdin" if test.stdin is not None else None
        stdout = "stdout" if test.stdout is not None else None
        stderr = "stderr" if test.stderr is not None else None
        files_in = [
            path for (path, file) in test.files.items() if file.input and path not in known_streams
        ]
        files_out = [
            path
            for (path, file) in test.files.items()
            if not file.input and path not in known_streams
        ]

        data = dict(
            name=name,
            title=title,
            exit_code=exit_code,
            args=args,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            files_in=files_in,
            files_out=files_out,
        )
        content += f"tests.append({repr(data)})\n"

    with open(SCRIPT_TEMPLATE) as f:
        script = f.read()
    script = script.replace("###GENERATED###", content)

    return io.BytesIO(script.encode("utf8"))
