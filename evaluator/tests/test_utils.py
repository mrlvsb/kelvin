import pytest
from evaluator.utils import parse_human_size


def test_human_size():
    assert parse_human_size(1024) == 1024
    assert parse_human_size("1024") == 1024
    assert parse_human_size("1024 ") == 1024
    assert parse_human_size("1024 B") == 1024
    assert parse_human_size("1024B") == 1024
    assert parse_human_size("5 KB") == 5 * 1024
    assert parse_human_size("5KB") == 5 * 1024
    assert parse_human_size("5K") == 5 * 1024
    assert parse_human_size("1.5M") == 1.5 * 1024 * 1024

    with pytest.raises(ValueError):
        parse_human_size("1.5Z")
