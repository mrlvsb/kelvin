import pytest

from evaluator.evaluation import InvalidWorkflowYaml, WorkflowConfig


def test_parse_empty_config():
    with pytest.raises(InvalidWorkflowYaml):
        WorkflowConfig.parse("")


def test_parse_non_dict():
    with pytest.raises(InvalidWorkflowYaml):
        WorkflowConfig.parse("- item1\n- item2")


def test_parse_defaults():
    result = WorkflowConfig.parse("pipeline: []")
    assert result.config.queue == "evaluator"
    assert result.config.timeout == 180
    assert result.config.tests == []
    assert result.config.jobs == []


def test_parse_queue_and_timeout():
    config = """
pipeline: []
queue: cuda
timeout: 60
"""
    result = WorkflowConfig.parse(config)
    assert result.config.queue == "cuda"
    assert result.config.timeout == 60


def test_parse_tests():
    config = """
pipeline: []
tests:
  - name: '00'
    title: first test
    exit_code: 0
    args: []
  - name: '01'
    title: second test
    args: [a, b]
"""
    result = WorkflowConfig.parse(config)
    assert len(result.config.tests) == 2
    assert result.config.tests[0].name == "00"
    assert result.config.tests[0].title == "first test"
    assert result.config.tests[0].exit_code == 0
    assert result.config.tests[1].name == "01"
    assert result.config.tests[1].args == ["a", "b"]


def test_parse_unknown_keys():
    config = """
pipeline: []
foo: bar
baz: 1
"""
    result = WorkflowConfig.parse(config)
    assert sorted(result.unknown_keys) == ["baz", "foo"]


def test_parse_async_key_ignored():
    config = """
pipeline: []
async: true
"""
    result = WorkflowConfig.parse(config)
    assert result.unknown_keys == []


def test_parse_job_options():
    config = """
pipeline:
    - type: gcc
      foo: bar
      title: BAZ
      fail_on_error: false
"""
    config = WorkflowConfig.parse(config).config
    assert len(config.jobs) == 1

    job = config.jobs[0]
    assert job.title == "BAZ"
    assert not job.fail_on_error
