import urllib.parse

from django.core.cache import cache
from typing import Dict, List, Optional

import serde

from . import config, dto, utils


# Actual INBUS API calls

def person_by_login(login: str) -> Optional[dto.PersonSimple]:
    url = urllib.parse.urljoin(config.INBUS_SERVICE_IDM_URL, f'person/login/{login}')

    person_resp = utils.inbus_request(url, {})
    if not person_resp:
        return None
    person_json = person_resp.json()

    # INBUS may return response that has missing fields
    if 'login' not in person_json:
        return None

    person_simple = dto.PersonSimple(login=person_json["login"].upper(), first_name=person_json.get('firstName', ''), second_name=person_json.get('secondName', ''),
                                full_name=person_json.get('fullName', ''), email=person_json.get('email', ''))

    return person_simple


def subject_versions(department_id: dto.DepartmentId = 386) -> List[dto.SubjectVersion]:
    """
    Get list of all subjects and their versions by department.
    Here `386` is Department of Computer Science.
    """
    results_per_page = 20
    subject_versions = []
    offset = 0
    while True:
        url = urllib.parse.urljoin(config.INBUS_SERVICE_EDISON_URL, 'edu/subjectVersions')
        subject_versions_resp = utils.inbus_request(url, {'departmentId': department_id, 'offset': offset, 'limit': results_per_page})

        subject_versions_json = subject_versions_resp.json()

        for subject_version_json in subject_versions_json:
            subject_json = subject_version_json['subject']
            subject_guarantee = serde.from_dict(dto.Person, subject_version_json['guarantee'])
            subject_version_guarantee = serde.from_dict(dto.Person, subject_json['guarantee'])
            subject = dto.Subject(subjectId=subject_json['subjectId'], code=subject_json['code'], abbrev=subject_json['abbrev'],
                                title=subject_json['title'], guarantee=subject_guarantee)
            subject_version =  dto.SubjectVersion(subjectVersionId=subject_version_json['subjectVersionId'], subject=subject,
                                                subjectVersionCompleteCode=subject_version_json['subjectVersionCompleteCode'], guarantee=subject_version_guarantee)

            subject_versions.append(subject_version)

        results = len(subject_versions_json)

        offset += results

        if results == 0:
            break

    return subject_versions


# Kelvin's interface

def search_user(login: str) -> Optional[dto.PersonSimple]:
    person_inbus = person_by_login(login)

    return person_inbus