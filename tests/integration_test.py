import asyncio
from contextlib import contextmanager

import pytest
import time

from lndngigs.event_listing import EventListing, LastFmApi, SongkickApi
from lndngigs.async_event_listing import AsyncSongkickApi, AsyncEventListing
from lndngigs.async_event_listing2 import AsyncEventListing2
from lndngigs.factories import get_logger
from lndngigs.utils import Config


@contextmanager
def timer():
    start = time.time()
    yield
    print("Elapsed: {}".format(time.time() - start))

@pytest.fixture()
def logger():
    return get_logger(True)


@pytest.fixture()
def config():
    return Config()


@pytest.fixture()
def lastfm_api(config, logger):
    return LastFmApi(logger=logger, lastfm_api_key=config.LASTFM_API_KEY, lastfm_api_secret=config.LASTFM_API_SECRET)


@pytest.fixture()
def songkick_api():
    return SongkickApi()


@pytest.fixture()
def event_listing(songkick_api: SongkickApi, lastfm_api: LastFmApi):
    return EventListing(
        songkick_api=songkick_api,
        lastfm_api=lastfm_api
    )

@pytest.mark.skip()
def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10


@pytest.mark.skip()
def test_lastfm_api_with_unknown_artist(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("foobarbaz___123!")
    assert len(tags) == 0


@pytest.mark.skip()
def test_event_with_tags(event_listing: EventListing):
    events_with_tags = event_listing.get_events(
        location=event_listing.parse_event_location("london"),
        events_date=event_listing.parse_event_date("monday")
    )
    assert len(list(events_with_tags)) > 0


@pytest.mark.skip()
def test_songkick_scraper(songkick_api: SongkickApi):
    events = songkick_api.get_events(
        location=songkick_api.parse_event_location("london"),
        events_date=songkick_api.parse_event_date("monday")
    )
    assert len(list(events)) > 0


@pytest.mark.skip()
def test_async_songkick_scraper(logger):
    event_listing = AsyncSongkickApi(logger, asyncio.get_event_loop())
    events = event_listing.get_events(
        event_listing.parse_event_location("london"),
        event_listing.parse_event_date("saturday")
    )
    assert len(list(events)) > 10  # At least 10 events in london on a saturday night


def test_async_event_listing(logger, lastfm_api: LastFmApi):
    with timer():
        event_loop = asyncio.get_event_loop()
        event_listing = AsyncEventListing(
            event_loop=event_loop,
            songkick_api=AsyncSongkickApi(logger=logger, event_loop=event_loop),
            lastfm_api=lastfm_api
        )
        events = event_listing.get_events(
            event_listing.parse_event_location("london"),
            event_listing.parse_event_date("saturday")
        )
        assert len(list(events)) > 10  # At least 10 events in london on a saturday night


def test_async_event_listing2(logger, lastfm_api: LastFmApi):
    with timer():
        event_loop = asyncio.get_event_loop()
        event_listing = AsyncEventListing2(
            logger=logger,
            event_loop=event_loop,
            lastfm_api=lastfm_api
        )
        events = event_listing.get_events(
            event_listing.parse_event_location("london"),
            event_listing.parse_event_date("saturday")
        )
        assert len(list(events)) > 10  # At least 10 events in london on a saturday night
