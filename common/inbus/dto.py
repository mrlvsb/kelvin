from dataclasses import dataclass
from typing import NewType

import serde

DepartmentId = NewType('DepartmentId', int)


@dataclass
class PersonSimple:
    """
    Info about person provided by DTO from INBUS. Not all attributes are present since we don't need them.
    Attribute names are in PEP-8 convention.
    """
    login: str
    full_name: str
    first_name: str
    second_name: str
    email: str


@serde.serde
@dataclass
class Person:
    personId: int
    login: str
    fullName: str


@dataclass
class Subject:
    subjectId: int
    code: str
    abbrev: str
    title: str
    guarantee: Person


@serde.serde
@dataclass
class SubjectVersion:
    subjectVersionId: int
    subject: Subject
    subjectVersionCompleteCode: str
    guarantee: Person