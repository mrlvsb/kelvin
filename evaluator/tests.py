import unittest
import os
import struct

from .evaluator import *
from .comparators import *
from .pipelines import GccPipeline

base_dir = os.path.dirname(__file__)


class TestEvaluation(unittest.TestCase):
    def evaluate(self, name, submit='submit.c'):
        path = os.path.join(base_dir, f'tests/{name}')
        r = evaluate(path, os.path.join(path, submit), '/tmp/eval')
        return list(r)[0]['tests'][0]

    def test_stdout_only(self):
        res = self.evaluate('stdout_only')

        self.assertEqual(res['stdout']['actual'].read(), 'Hello world\n')
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_stdout_only_wrong(self):
        res = self.evaluate('stdout_only', 'submit_wrong.c')

        self.assertEqual(res['stdout']['actual'].read(), 'foo bar\n')
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertFalse(res['success'])
        # TODO: check html result

    def test_stdout_binary_in_text(self):
        res = self.evaluate('stdout_only', 'binary.c')

        self.assertEqual(res['stdout']['actual'].read('rb'), struct.pack("10I", *range(120, 130)))
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertFalse(res['success'])
        # TODO: check html result

    def test_binary_stdout_only(self):
        res = self.evaluate('binary_stdout', 'submit.c')

        self.assertEqual(res['stdout']['actual'].read('rb'), struct.pack("10I", *range(120, 130)))
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])
        # TODO: check html result

    def test_stdin_stdout(self):
        res = self.evaluate('stdin_stdout')

        self.assertEqual(res['stdout']['actual'].read(), 'HELLO')
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_stdin_stdout_wrong(self):
        res = self.evaluate('stdin_stdout', 'wrong.c')

        self.assertEqual(res['stdout']['actual'].read(), 'hello')
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertFalse(res['success'])

    def test_stderr(self):
        res = self.evaluate('stderr_only')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr']['actual'].read(), 'error...\n')
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_stderr_wrong(self):
        res = self.evaluate('stderr_only', 'wrong.c')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr']['actual'].read(), 'hmmm...\n')
        self.assertEqual(res['exit_code'], 0)
        self.assertFalse(res['success'])

    def test_exit_code(self):
        res = self.evaluate('exit_code')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 42)
        self.assertTrue(res['success'])

    def test_cmdline(self):
        res = self.evaluate('cmdline')

        self.assertEqual(res['stdout']['actual'].read(), '"first" "second" "third with a space" ')
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertTrue(res['success'])

    def test_file(self):
        res = self.evaluate('text_file')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual(len(res.files), 1)
        self.assertEqual(res.files['test.txt']['actual'].read(), 'hello file!\nfoo bar\n')
        self.assertTrue(res['success'])

    def test_file_wrong_path(self):
        res = self.evaluate('text_file', 'wrong_path.c')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual(len(res.files), 1)
        self.assertTrue('actual' not in res.files['test.txt'])
        self.assertEqual(res.files['test.txt']['error'], 'file not found')
        self.assertFalse(res['success'])

    def test_file_bin_in_txt(self):
        res = self.evaluate('text_file', 'bin.c')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual(len(res.files), 1)
        self.assertEqual(res.files['test.txt']['actual'].read('rb'), b'\xb4')
        self.assertTrue('error' not in res.files['test.txt'])
        self.assertFalse(res['success'])

    def test_multiple_files(self):
        res = self.evaluate('multiple_files')

        self.assertEqual(res['stdout'], None)
        self.assertEqual(res['stderr'], None)
        self.assertEqual(res['exit_code'], 0)
        self.assertEqual(len(res.files), 2)
        self.assertEqual(res.files['first.txt']['actual'].read(), 'first\n')
        self.assertEqual(res.files['second.txt']['actual'].read(), 'second\n')
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
        res = self.evaluate('large_output')
        self.assertEqual(len(res.files['stdout']['actual'].read()), 1024 * 1024)
        self.assertFalse(res['success'])

    def test_custom_check(self):
        res = self.evaluate('custom_check')
        self.assertTrue(res['processed'])
        self.assertTrue(res['success'])
    

class TestComparators(unittest.TestCase):
    def file(self, name):
        return os.path.join(base_dir, 'tests', 'comparators', name)

    def test_open_text(self):
        expected = ['0', '1', '2', '3', '4', '5']

        self.assertEqual(list(open_me(map(str, range(6)))), expected)
        self.assertEqual(list(open_me(self.file("seq5"))), expected)
        self.assertEqual(list(open_me(io.StringIO("0\n1\n2\n3\n4\n5"))), expected)

    def test_open_strlower(self):
        expected = ['hello world', 'foo! 128 bar']
        self.assertEqual(list(open_me(self.file("strlower"), 't', filters=['lower'])), expected)
        

    def test_open_binary(self):
        expected = [struct.pack("I", i) for i in range(6)]

        self.assertEqual(list(open_me((struct.pack("I", i) for i in range(6)))), expected)
        self.assertEqual(list(open_me(self.file("seq5.bin"), 'b', block_size=4)), expected)
        self.assertEqual(list(open_me(io.BytesIO(struct.pack("6I", *range(6))), block_size=4)), expected)

    def test_stringio_same(self):
        success, result = text_compare(io.StringIO("test 12345\nxyz"), io.StringIO("test 12345\nxyz"))

        self.assertTrue(success)
        self.assertEqual(result, "")

    def test_file_same(self):
        success, result = text_compare(self.file("same.1"), self.file("same.1"))

        self.assertTrue(success)
        self.assertEqual(result, "")

    def test_generator_same(self):
        success, result = text_compare((i for i in range(10)), (i for i in range(10)))

        self.assertTrue(success)
        self.assertEqual(result, "")


    def test_file_differs(self):
        success, result = text_compare(self.file("same.1"), self.file("copy.2"))

        self.assertFalse(success)
        self.assertEqual(result, "")


if __name__ == '__main__':
    unittest.main()