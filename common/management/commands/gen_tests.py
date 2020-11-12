from django.core.management.base import BaseCommand, CommandError
from evaluator.testsets import TestSet
import subprocess
import shlex
import os
import re
import shutil

class Command(BaseCommand):
    def handle(self, *args, **opts):
        testset = TestSet('.')
        for action in testset.pipeline:
            if action.type == 'gcc':
                flags = action.kwargs.get('flags', '')
                subprocess.check_call(['gcc', 'solution.c', '-o', 'solution', *shlex.split(flags.replace('-fsanitize=address', ''))])

        for test in testset:
            delete = []

            for name, f in test.files.items():
                if f.input and name not in ['stdin', 'stdout']:
                    delete.append(name)
                    shutil.copyfile(f"{test.name}.file_in.{name}", name)

            with open(f'{test.name}.out', 'wb') as out, open(f'{test.name}.err', 'wb') as err:
                p = subprocess.Popen(['strace', '-o', '.strace', '-eopenat', './solution', *test.args], stdout=out, stderr=err)
                p.wait()

            with open('.strace') as f:
                for line in f:
                    m = re.match(r'openat\(AT_FDCWD, "([^"]+)", ([^) ]+)', line)
                    if m:
                        path = m.group(1)
                        mods = m.group(2)
                        if 'WR' in mods:
                            os.rename(path, f"{test.name}.file_out.{path}")

            for f in delete:
                os.unlink(f)
        
        for f in os.listdir('.'):
            if os.stat(f).st_size == 0:
                os.unlink(f)

        try:
            os.unlink('.strace')
        except FileNotFoundError:
            pass