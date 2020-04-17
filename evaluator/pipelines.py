import tarfile

class CommandPipe:
    def __init__(self, commands):
        self.commands = commands

    def run(self, evaluation):
        output = ""
        for command in self.commands:
            result = evaluation.sandbox.run(command, )
            output += f"<code>$ {command}</code><br><pre>{result['stdout']}</pre>" 

        return {
            "html": output,
        }


class TestsPipe:
    def run(self, evaluation):
        results = []
        for test in evaluation.tests:
            results.append(evaluation.evaluate(self.id, test))

        return {
            "tests": results,
        }

class GccPipeline:
    def __init__(self, name, gcc_params=[]):
        self.name = name
        self.gcc_params = gcc_params

    def run(self, evaluation):
        # TODO: params formatting is not secure!
        gcc_result = evaluation.sandbox.compile(self.gcc_params + evaluation.tests.gcc_flags)

        results = []

        if gcc_result['exit_code'] == 0:
            for test in evaluation.tests:
                results.append(evaluation.evaluate(self.name, test))
           
        return {
            "gcc": gcc_result,
            "tests": results,
        }

class Mallocer:
    wrapper = """
#include <stdio.h>
#include <memory.h>
#include <stdlib.h>

static int failed;
static int fail_at = -1;

void *__real_malloc(size_t size);
void* __wrap_malloc (size_t c) {
  if(fail_at == -1) {
    char *env = getenv("__MALLOC_FAIL");
    if(env) {
      fail_at = atoi(env);
    }
  }

  if(failed >= fail_at) {
    return NULL;
  }
  failed++;

  return __real_malloc (c);
}
    """

    def __init__(self, max_fails=10):
        self.max_fails = max_fails

    def run(self, evaluation):
        with evaluation.sandbox.open_temporary("malloc.c") as f:
            f.write(self.wrapper)
            f.close()

            gcc_result = evaluation.sandbox.compile(["-Wl,--wrap=malloc", '-fsanitize=address'])

            results = []
            for test in evaluation.tests:
                for i in range(self.max_fails):
                    env = {'__MALLOC_FAIL': i}
                    result = evaluation.evaluate(test, env=env, title=f"{test.name} fails at malloc call #{i+1}")
                    if not result['success']:
                        # TODO: detect kill from sanitizer
                        result['success'] = result['exit_code'] != 0 and 'AddressSanitizer' not in result['stderr']

                    results.append(result)

            return {
                "gcc": gcc_result,
                "tests": results,
            }
        
class InputGeneratorPipe:
    def __init__(self, path='input_generator.py', count=4):
        self.gen_path = path
        self.count = count


    def run(self, evaluation):
        gcc_result = evaluation.sandbox.compile(['-fsanitize=address'])
        path = evaluation.task_file(self.gen_path)

        if not os.path.exists(path):
            return

        results = []
        for i in range(self.count):
            with tempfile.NamedTemporaryFile() as stdin, tempfile.NamedTemporaryFile() as stdout, tempfile.NamedTemporaryFile() as stderr:
                p = subprocess.Popen(["python3", path], stdout=stdin)
                p.wait()

                stdin.seek(0)

                p = subprocess.Popen([evaluation.task_file('solution')], stdin=stdin, stdout=stdout, stderr=stderr)
                p.wait()

                test = Test(f"random {i}")
                test.stdin = stdin.name
                test.stdout = stdout.name
                test.stderr = stderr.name
                results.append(evaluation.evaluate(test))
            
        
        return {
            'gcc': gcc_result,
            'tests': results,
        }
