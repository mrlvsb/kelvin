import unittest

from evaluator import *

class TestStringMethods(unittest.TestCase):
    def evaluate(self, name):
        s = Sandbox()
        s.copy(f'tests/{name}/submit.c', "main.c")

        e = Evaluation(f'tests/{name}/', s)
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
        s.copy(f'tests/warning.c', "main.c")

        e = Evaluation('/xx', s)
        res = GccPipeline().run(e)
            
        self.assertTrue("implicit declaration of function ‘printf’" in res['gcc']['stderr'])

    def test_error(self):
        s = Sandbox()
        s.copy(f'tests/error.c', "main.c")

        e = Evaluation('/xx', s)
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
            
    

if __name__ == '__main__':
    unittest.main()