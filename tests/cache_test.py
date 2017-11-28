from datetime import date, timedelta
from random import randint
from time import sleep

import os

import logging
import pytest
import redis

from lndngigs.event_listing import CachedEventListing
from lndngigs.utils import CommandMessagesQueue
from lndngigs.entities import Artist, Event


class EventListingMock():
    def __init__(self):
        self._events = {}

    def set_events(self, location, events_date, events):
        if location not in self._events:
            self._events[location] = {}
        self._events[location][events_date] = events

    def get_events(self, location, events_date):
        try:
            yield from self._events[location][events_date]
        except KeyError:
            pass


@pytest.fixture()
def event_listing_mock():
    return EventListingMock()


@pytest.fixture()
def redis_client():
    assert "REDIS_URL" in os.environ, "Cannot test redis integration without REDIS_URL env var being set"
    return redis.from_url(os.environ["REDIS_URL"])


def test_cached_events_warms_up_and_hits_the_cache(event_listing_mock, redis_client):
    events1 = [
        Event(
            artists=[Artist("Radiohead", ["Rock", "Awesome", "Thom Yorke"], "http://lndngigs/radiohead.jpg")],
            venue="Roundhouse",
            link="http://doesnt-really-matter.com/radiohead-at-roundhouse"
        )
    ]

    events2 = events1 + [
        Event(
            artists=[
                Artist("Black Sabbath", ["Heavy"], "http://lndngigs/black-sabbat.jpg"),
                Artist("Soundgarden", ["Grunge", "Hard Rock", "Legendary"], "http://lndngigs/soundgarden.jpg"),
                Artist("Faith No More", [], "http://lndngigs/faith-no-more.jpg"),
                Artist("Motorhead", [], None)
            ],
            venue="Hyde Park",
            link="http://doesnt-really-matter.com/british-summer-time-2015"
        )
    ]

    seconds = 1

    cached_event_listing = CachedEventListing(
        logger=logging.getLogger("test"),
        event_listing=event_listing_mock,
        redis_client=redis_client,
        cache_ttl=timedelta(seconds=seconds)
    )

    location = "cthulhu"
    events_date = date(year=1990, day=1, month=1) + timedelta(days=randint(0, 365 * 30))  # Random date between 1990 and 2010

    # Warm up the cache
    event_listing_mock.set_events(location=location, events_date=events_date, events=events1)
    assert list(cached_event_listing.get_events(location=location, events_date=events_date)) == events1

    # Hit the cache
    event_listing_mock.set_events(location=location, events_date=events_date, events=events2)
    assert list(cached_event_listing.get_events(location=location, events_date=events_date)) == events1

    sleep(seconds)

    # Cache expired by now: will get fresh events and cache them again
    assert list(cached_event_listing.get_events(location=location, events_date=events_date)) == events2


def test_queue_messages(redis_client):
    message = {"foo": "bar"}

    queue = CommandMessagesQueue(redis_client=redis_client)
    queue.push(message)
    assert queue.pop() == message
