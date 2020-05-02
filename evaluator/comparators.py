import io
import numpy as np
from PIL import Image
import base64
import tempfile
import subprocess

from evaluator import image_evaluator


def apply_filters(line, filters):
    for f in filters:
        line = f.filter(line)
    return line
   

def xx(resource, filters=[]):
    with resource:
        for line in resource:
            if line[-1] == '\n':
                yield apply_filters(line[:-1], filters)
            else:
                yield apply_filters(line, filters)

def xxbin(f, block_size=1024):
    with f:
        while True:
            b = f.read(block_size)
            if b == b'':
                break
            yield b


def open_me(resource, mode='t', block_size=None, filters=[]):
    if isinstance(resource, str):
        if mode == 't':
            resource = open(resource, errors='replace')
        elif mode == 'b':
            resource = open(resource, 'rb')
        else:
            raise NotImplementedError("mode not implemented")

    if isinstance(resource, io.TextIOBase):
        return xx(resource, filters)
    elif isinstance(resource, io.IOBase):
        return xxbin(resource, block_size=block_size)
    
    return resource

def text_compare(expected, actual, filters=[]):
    try:
        expected = open_me(expected, filters=filters)
        actual = open_me(actual, filters=filters)

        with tempfile.NamedTemporaryFile() as exp, tempfile.NamedTemporaryFile() as act, tempfile.TemporaryFile() as out:
            exp.write(("\n".join(expected)).encode('utf-8'))
            exp.flush()
            act.write(("\n".join(actual)).encode('utf-8'))
            act.flush()

            cmd = [
                "diff",
                "-a",
                "-u",
                act.name,
                exp.name,
            ]

            p = subprocess.Popen(cmd, stdout=out)
            p.communicate()

            success = p.returncode == 0

            out.seek(0)
            return success, None, out.read().decode('utf-8')
    except UnicodeDecodeError as e:
        return False, str(e)


def binary_compare(f1, f2):
    f1 = open_me(f1, 'b', block_size=4)
    f2 = open_me(f2, 'b', block_size=4)

    errors = []
    for a, b in zip(f1, f2):
        if a != b:
            errors.append("not matches!!!")

    return (False if errors else True, ''.join(errors))


def to_base64(array):
    with io.BytesIO() as f:
        img = Image.fromarray(array)
        img.save(f, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(f.getvalue()).decode('utf-8')

def image_compare(f1, f2):
    diff_img, expected_img = image_evaluator.compare(f1, f2)
    color_diff_img = image_evaluator.colorize_diff(expected_img, diff_img)
    actual = np.array(Image.open(f2))

    return (True, f"expected:<br><img src='{to_base64(expected_img)}'><br>actual:<br> <img src='{to_base64(actual)}'><br>diff:<br> <img src='{to_base64(color_diff_img)}'>")
