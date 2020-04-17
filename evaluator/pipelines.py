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
