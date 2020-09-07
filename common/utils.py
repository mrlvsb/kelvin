from datetime import timedelta
import re

def is_teacher(user):
    return user.groups.filter(name='teachers').exists()

def parse_time_interval(text):
    patterns = [
        r"(?P<days>\d+)\s*(d|day|days)",
        r"(?P<minutes>\d+)\s*(m|min|minute|minutes)",
        r"(?P<hours>\d+)\s*(h|hour|hours)",
        r"(?P<weeks>\d+)\s*(w|week|weeks)",
    ]

    parsed = {}
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            parsed = {**parsed, **{k: int(v) for k, v in match.groupdict().items()}}
    return timedelta(**parsed)
