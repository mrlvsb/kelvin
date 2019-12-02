import unittest
import os

from .evaluator import *
from .pipelines import GccPipeline

base_dir = os.path.dirname(__file__)


class TestStringMethods(unittest.TestCase):
    def evaluate(self, name):

        s = Sandbox()
        s.copy(os.path.join(base_dir, f'tests/{name}/submit.c'), "main.c")

        e = Evaluation(os.path.join(base_dir, f'tests/{name}/'), '/tmp/kelvin', s)
        r = GccPipeline().run(e)

        return r['tests'][0]

    def test_stdout_only(self):
        res = self.evaluate('stdout_only')

        self.assertEqual(res['stdout'], 'Hello world\n')
        self.assertEqual(res['stderr'], '')
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_exit_code(self):
        res = self.evaluate('exit_code')

        self.assertEqual(res['stdout'], '')
        self.assertEqual(res['stderr'], '')
        self.assertEqual(res['exit_code'], 42)
        self.assertTrue(res['success'])

    def test_stdin_stdout(self):
        res = self.evaluate('stdin_stdout')

        self.assertEqual(res['stdout'], 'HELLO\n')
        self.assertEqual(res['stderr'], '')
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_stderr(self):
        res = self.evaluate('stderr_only')

        self.assertEqual(res['stdout'], '')
        self.assertEqual(res['stderr'], 'error...\n')
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_cmdline(self):
        res = self.evaluate('cmdline')

        self.assertEqual(res['stdout'], '"first" "second" "third with a space" ')
        self.assertEqual(res['stderr'], '')
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_file(self):
        res = self.evaluate('file')

        self.assertEqual(res['stdout'], '')
        self.assertEqual(res['stderr'], '')
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual(len(res['files']), 1)
        self.assertEqual(res['files'][0]['content'], 'hello file!\n')
        self.assertTrue(res['success'])

    def test_warnings(self):
        s = Sandbox()
        s.copy(os.path.join(base_dir, f'tests/warning.c'), "main.c")

        e = Evaluation('/xx', '/tmp/kelvin', s)
        res = GccPipeline().run(e)
            
        self.assertTrue("implicit declaration of function ‘printf’" in res['gcc']['stderr'])

    def test_error(self):
        s = Sandbox()
        s.copy(os.path.join(base_dir, f'tests/error.c'), "main.c")

        e = Evaluation('/xx', '/tmp/kelvin', s)
        res = GccPipeline().run(e)
            
        self.assertTrue("error: ld returned 1 exit status" in res['gcc']['stderr'])

    def test_whitespace_end(self):
        for t in ['whitespace_end', 'whitespace_all']:
            res = self.evaluate(t)
            self.assertTrue(res['success'])

    def test_large_output(self):
        s = Sandbox()
        res = s.run("/bin/dd if=/dev/zero bs=64M count=1")
        self.assertEqual(len(res['stdout']), 64 * 1024 * 1024)

    def test_custom_check(self):
        res = self.evaluate('custom_check')
        self.assertTrue(res['processed'])
        self.assertTrue(res['success'])
    

if __name__ == '__main__':
    unittest.main()