from dataclasses import is_dataclass, fields
from enum import Enum
from typing import Any, TypeVar, Dict, Type


def dataclass_to_dict(obj: Any) -> Any:
    """
    Recursively converts a dataclass (or nested dataclasses) into a dictionary.

    This function safely serializes dataclass instances, including:
    - Nested dataclasses
    - Enums (converted to their `.value`)
    - Lists and dictionaries containing dataclasses or enums

    Returns a dictionary representation of the dataclass.
    """

    if isinstance(obj, Enum):
        return obj.value
    elif is_dataclass(obj):
        return {field.name: dataclass_to_dict(getattr(obj, field.name)) for field in fields(obj)}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: dataclass_to_dict(value) for key, value in obj.items()}
    else:
        return obj


T = TypeVar("T")


def dict_to_dataclass(data: Dict[str, Any], cls: Type[T]) -> T:
    """
    Recursively constructs a dataclass instance from a dictionary.

    This function reverses the transformation made by `dataclass_to_dict`.
    It supports:
    - Nested dataclasses
    - Lists of dataclasses
    - Enum reconstruction (from both names and values)

    Returns an instance of the specified dataclass, parsed from the dictionary.
    """

    init_args = {}
    for field_def in fields(cls):
        field_value = data.get(field_def.name)
        field_type = field_def.type

        if field_value is None:
            init_args[field_def.name] = None
            continue

        if is_dataclass(field_type):
            init_args[field_def.name] = dict_to_dataclass(field_value, field_type)
        elif hasattr(field_type, "__origin__") and field_type.__origin__ is list:
            inner_type = field_type.__args__[0]
            init_args[field_def.name] = [
                dict_to_dataclass(item, inner_type) if is_dataclass(inner_type) else item
                for item in field_value
            ]
        elif isinstance(field_value, str) and issubclass(field_type, Enum):
            init_args[field_def.name] = field_type(field_value)
        elif isinstance(field_value, str) and hasattr(field_type, "__members__"):
            init_args[field_def.name] = field_type[field_value]
        elif hasattr(field_type, "__members__"):
            init_args[field_def.name] = field_type(field_value)
        else:
            init_args[field_def.name] = field_value

    return cls(**init_args)
