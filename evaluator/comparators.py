import io
import tempfile
import subprocess

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
                "-i",
                "-w",
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
    print(f1)
    f1 = open_me(f1, 'b', block_size=1)
    f2 = open_me(f2, 'b', block_size=1)

    try:
        expected = f1
        actual = f2

        with tempfile.NamedTemporaryFile('wt') as exp, tempfile.NamedTemporaryFile('wt') as act, tempfile.TemporaryFile() as out:
            exp.write(" ".join([x.hex() for x in expected]))
            exp.flush()
            act.write(" ".join([x.hex() for x in actual]))
            act.flush()

            cmd = [
                "diff",
                "-a",
                "-u",
                "-i",
                "-w",
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

