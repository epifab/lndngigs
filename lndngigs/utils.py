import json
import os
import time
from datetime import date, timedelta, datetime

from redis import Redis


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
        return datetime.strptime(date_str, '%d-%m-%Y').date()


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
        self.LASTFM_API_KEY = self.get("LASTFM_API_KEY")
        self.LASTFM_API_SECRET = self.get("LASTFM_API_SECRET")
        self.SLACK_API_TOKEN = self.get("SLACK_API_TOKEN")
        self.SLACK_VALIDATION_TOKEN = self.get("SLACK_VALIDATION_TOKEN")
        self.REDIS_URL = self.get("REDIS_URL")
        self.DEBUG = self.get("DEBUG", convert=bool, default=False)


class CommandMessagesQueue:
    QUEUE_NAME = "slack-commands"

    def __init__(self, redis_client: Redis, message_ttl=timedelta(seconds=10)):
        self._redis_client = redis_client
        self._message_ttl = message_ttl

    def push(self, message):
        self._redis_client.lpush(self.QUEUE_NAME, json.dumps(message).encode("utf-8"))

    def pop(self):
        while True:
            message = self._redis_client.rpop(self.QUEUE_NAME)
            if message is None:
                time.sleep(0.1)
            else:
                return json.loads(message.decode("utf-8"))

    def messages(self):
        while True:
            yield self.pop()
