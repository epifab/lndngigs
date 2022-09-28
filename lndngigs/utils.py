import os
from datetime import date, timedelta, datetime


class ValidationException(Exception):
    pass


def parse_date(date_str):
    weekdays = [
        ('monday', 'mon'),
        ('tuesday', 'tue'),
        ('wednesday', 'wed'),
        ('thursday', 'thu'),
        ('friday', 'fri'),
        ('saturday', 'sat'),
        ('sunday', 'sun')
    ]

    date_str = date_str.lower().strip()

    if date_str == 'today':
        return date.today()
    elif date_str == 'tomorrow':
        return date.today() + timedelta(days=1)
    else:
        for weekday_index, weekday_names in enumerate(weekdays):
            if date_str in weekday_names:
                day = date.today()
                while day.weekday() != weekday_index:
                    day += timedelta(days=1)
                return day
        return datetime.strptime(date_str, '%Y-%m-%d').date()


class Config:
    def get(self, key, **kwargs):
        if not key in os.environ:
            if "default" not in kwargs:
                raise Exception("Environment variable '{}' is missing".format(key))
            else:
                return kwargs["default"]
        try:
            return kwargs["convert"](os.environ[key]) if "convert" in kwargs else os.environ[key]
        except:
            raise Exception("Variable '{}' is invalid".format(key))

    def __init__(self):
        self.REDIS_URL = self.get("REDIS_URL", default=None)
        self.DEBUG = self.get("DEBUG", convert=bool, default=False)
