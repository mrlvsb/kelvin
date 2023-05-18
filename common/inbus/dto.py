from dataclasses import dataclass

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

