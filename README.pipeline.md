# Pipeline configuration
Pipeline actions are executed when a student submits a new solution.
It can be used to build a submitted program to check if all parts of source code were uploaded or evaluate the solution against prepared tests.

Actions are defined in `config.yml` file in the task directory.

<a href="https://github.com/mrlvsb/kelvin/blob/master/evaluator/pipelines.py">Builtin actions</a> are implemented directly in Kelvin source code, but it is also possible to run the action in <a href="https://github.com/mrlvsb/kelvin/tree/master/evaluator/images">docker container</a> with concrete compilers, so they don't need to be installed on the server.

## gcc
Action for compiling all source codes in a submitted solution with or without a makefile.
The errors and warnings are shown in the Result tab.


```yaml
pipeline:
  - type: gcc
    output: main
    flags: -Wall -Wextra -g -fsanitize=address
    ldflags: -lm
```

## Tests
Verifies the student's program against predefined input/output/files tests.
All tests are automatically collected and provided to students.

Tests must be enabled in the pipeline:

```yaml
pipeline:
  - type: gcc
  - type: tests

```

Static tests can be defined by files in the task directory.
In these examples, the first line with the hash denotes filename.
These files are grouped together by the matching filename prefix, which denotes a single test or a scenario.
It is recommended to prepend the test number to each test because tests are ordered by name.


### The sandbox environment limits
Submits are evaluated in the sandboxed environment with the help of <a href="https://github.com/ioi/isolate">isolate tool</a>.
Executing the student's submit is constrained to the <a href="https://github.com/mrlvsb/kelvin/blob/63b6ffc294e3b91d1db13453d487c773764ba4a1/evaluator/testsets.py#L122">default</a> wall clock time, memory, number of created processes etc.
This can be overriden by the yaml configuration:

```yaml
limits:
  fsize: 5M  # max filesize  
  wall-time: 5 # max 5 seconds per test
  cg-mem: 5M # max 5MB of memory usage
```

### Check the standard output
This test will execute the student program and checks if it prints `2020` in the standard output.

```
# 01_year.out
2020
```

### Pass the standard input and check the standard output
The standard input is passed to the program and then the student's result on the output is compared to the expected stdout result.

```
# 02_sum.in
1 2 3 4
```
```
# 02_sum.out
10
```

### Check the file content
Checks if the student's program created file `result.txt` with the expected content.

```
# 03_nums.file_out.result.txt
1 2 3 4 5 6 7 8 9 10
```

### Provide an input file
Provides the input file `data.txt` to student's program.
It can be combined with stdout or file comparing. 

```
# 04_nums.file_in.data.txt
1 2 3 4 5 6 7 8 9 10
```

### Arguments
Arguments passed to the program can be defined in yaml configuration:

```yaml
tests:
  - name: 06_argumenty_programu
    title: 5. argumenty programu
    args:
      - 127.0.0.1
      - 80
```

### Exit code checking
Program's exit code must be zero in order to pass the test.
Different program's exit code or disabling of this check can be configured in yaml. 

```yaml
tests:
  - name: 07_exit_code
    exit_code: 42

  - name: 08_any_exit_code
    exit_code: null
```

### Filters
<a href="https://github.com/mrlvsb/kelvin/blob/63b6ffc294e3b91d1db13453d487c773764ba4a1/evaluator/filters.py#L30">Filters</a> are used for tolerant checking the outputs.
It can ignore any whitespaces or make a case insensitive comparing.
It was also possible to find the line with the answer in the output...

```yaml
filters:
  - rstrip # remove the spaces after the last character on the line
  - lower  # make case insensitive comparing
```

## Dynamic tests
Some bigger or dynamic tests can be configured by `script.py` in the task directory.
Tests are created in the function `gen_tests` - you can also use numpy for generating the output for your random input.
This function can be also used for generating <a href="https://kelvin.cs.vsb.cz/#/task/edit/125">variants</a> of student tasks, that can be defined simply in <a href="https://kelvin.cs.vsb.cz/#/task/edit/124">markdown files</a>.


```python
# script.py
import random

def gen_tests(evaluation):
    r = random.randint(0, 100)

    test = evaluation.create_test("01_dynamic_test") 
    test.args = [f"input{r}.txt", f"output{r}.txt", str(r), evaluation.meta['login']]
    test.exit_code = r

    f = test.add_memory_file("stdin", input=True)
    f.write(f"stdin {evaluation.meta['login']}")

    f = test.add_memory_file("stdout")
    f.write(f"stdout {evaluation.meta['login']}")

    f = test.add_memory_file("stderr")
    f.write(f"stderr {evaluation.meta['login']}")

    f = test.add_memory_file("input.txt", input=True)
    f.write(f"input.txt {evaluation.meta['login']}")

    f = test.add_memory_file("output.txt")
    f.write(f"output.txt {evaluation.meta['login']}")
``` 

## Autograder
Automatically assigns points gained in tests evaluation.
Manually assigned points are replaced when the submit is reevaluated - you have been warned.

```yaml
pipeline:
  - type: auto_grader
    propose: false                 # show points in result instead of assigning them directly
    overwrite: false               # overwrite points if they are already assigned to THAT submit
    after_deadline_multiplier: 0.9 # give only 90% of maximal points for submits after the deadline
```

## clang-tidy
Adds comments to the source code from the clang-tidy linter.
Checks can give student's helpful feedback about leaker memory, misused pointer or misstyped assignment in a condition instead of comparison.

Individual <a href="https://clang.llvm.org/extra/clang-tidy/checks/list.html">checks</a> can be enabled or disabled.
Following example enables all checks `*` and disables `-` the remaining ones.

```yaml
pipeline:
 - type: clang-tidy 
    checks:
        - '*'
        - '-cppcoreguidelines-avoid-magic-numbers'
        - '-readability-magic-numbers'
        - '-cert-*'
        - '-llvm-include-order'
        - '-cppcoreguidelines-init-variables'
        - '-clang-analyzer-security*'
```

## run
Custom programs can be executed in a docker container.
This can be used for simply executing the students program and showing the result to the Results tab.

```yaml
pipeline:
  - type: run
    commands:    
      - ./main
      - ./main > out
      - cat /etc/passwd | ./main

      - cmd: timeout 2 ./main
        cmd_show: ./main

      - '# apt install faketime # executed but hidden from the output'
      
      - cmd: timeout 5 ./main || true
        cmd_show: ./main
        asciinema: true

      - display: ['*.ppm', '*.pgm', '*.jpg']
```


## Docker
Own private actions can be implemented in any language in a <a href="https://github.com/mrlvsb/kelvin/tree/master/evaluator/images">docker container</a> and published to the official docker hub.
Currently, the action has access to all source codes and artifacts from the previously executed actions like an executable file.
When the action starts, the docker entry point program is executed.
The action can generate `result.html` which will be shown in the Result tab to students.
