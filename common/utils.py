from datetime import datetime

def current_semester():
    now = datetime.now()

    if now.month >= 9 or now.month == 1:
        year = now.year
        if now.month == 1:
            year -= 1
        winter = 1
    else:
        year = now.year - 1
        winter = 0

    return year, winter
