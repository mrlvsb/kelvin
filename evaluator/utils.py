import io
import shutil
import re


def parse_human_size(txt):
    m = re.match(r'^([0-9]+(\.[0-9]+)?)\s*(K|M|G|T)?B?$', str(txt).strip())
    if not m:
        raise ValueError(f"Invalid size: {txt}")

    num = float(m.group(1))
    multipliers = ['K', 'M', 'G', 'T']

    mult = 1
    if m.group(3):
        mult = 2**(10 * (1 + multipliers.index(m.group(3))))

    return int(num * mult)


def copyfile(src, dst):
    if isinstance(src, io.StringIO):
        with open(dst, 'w') as f:
            f.write(src.getvalue())
    else:
        shutil.copyfile(src, dst)
