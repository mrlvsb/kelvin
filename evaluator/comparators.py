import io
from diff_match_patch import diff_match_patch

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
            resource = open(resource)
        elif mode == 'b':
            resource = open(resource, 'rb')
        else:
            raise NotImplementedError("mode not implemented")

    if isinstance(resource, io.TextIOBase):
        return xx(resource, filters)
    elif isinstance(resource, io.IOBase):
        return xxbin(resource, block_size=block_size)
    
    return resource



def text_compare(f1, f2, filters=[]):
    try:
        f1 = open_me(f1, filters=filters)
        f2 = open_me(f2, filters=filters)

        # materialize them :(
        text1 = "\n".join(f1)
        text2 = "\n".join(f2)

        dmp = diff_match_patch()
        diff = dmp.diff_main(text2, text1)
        html = dmp.diff_prettyHtml(diff)

        success = True
        for t, _ in diff:
            if t != 0:
                success = False
                break

        return success, html
    except UnicodeDecodeError as e:
        return False, e



def binary_compare(f1, f2):
    f1 = open_me(f1, 'b', block_size=4)
    f2 = open_me(f2, 'b', block_size=4)

    errors = []
    for a, b in zip(f1, f2):
        if a != b:
            errors.append("not matches!!!")

    return (False if errors else True, ''.join(errors))


def image_compare(f1, f2):
    #if f1 not File:
    #    raise "Only files can be compared"

    #np.array(open(f1).read()).diff(open(f2).read())....

    return (True, "<img src='data:image/png,base64;.....'>")


"""
# tasks/task.py
def init_tests():
    t = Test()
    t.stdout = (i for i in range(100))

#-Werror=array-bounds
#-Qformat_security
# odebirat body za warning?
"""