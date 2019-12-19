import io
import shutil


def copyfile(src, dst):
    if isinstance(src, io.StringIO):
        with open(dst, 'w') as f:
            f.write(src.getvalue())
    else:
        shutil.copyfile(src, dst)
