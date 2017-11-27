import asyncio
import json
from contextlib import contextmanager

import pytest
import time

from datetime import date
from flask.testing import FlaskClient

from lndngigs.event_listing import LastFmApi
from lndngigs.event_listingv3 import AsyncEventListing
from lndngigs.factories import get_logger
from lndngigs.utils import Config
from lndngigs.web import build_app


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
def flask_client(config, logger):
    return build_app(config, logger).test_client()


def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10


def test_lastfm_api_with_unknown_artist(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("foobarbaz___123!")
    assert len(tags) == 0


def test_event_listingv3(logger, lastfm_api: LastFmApi):
    with timer():
        event_loop = asyncio.get_event_loop()
        event_listing = AsyncEventListing(
            logger=logger,
            event_loop=event_loop,
            lastfm_api=lastfm_api
        )
        events = event_listing.get_events(
            event_listing.parse_event_location("london"),
            event_listing.parse_event_date("saturday")
        )
        assert len(list(events)) > 10  # At least 10 events in london on a saturday night


def test_index_endpoint(flask_client: FlaskClient):
    response = flask_client.get("/")
    assert response.status_code == 200


def test_gigs_endpoint(flask_client: FlaskClient):
    response = flask_client.get("/gigs/london/saturday")
    assert response.status_code == 200
    json_response = json.loads(response.data.decode("utf-8"))
    assert "gigs" in json_response
    assert len(json_response["gigs"]) > 10


def test_event_listing_with_utf8(logger, lastfm_api: LastFmApi):
    event_loop = asyncio.get_event_loop()
    event_listing = AsyncEventListing(
        logger=logger,
        event_loop=event_loop,
        lastfm_api=lastfm_api
    )
    event = event_loop.run_until_complete(event_listing.scrape_event(
        date.today(),
        "http://www.songkick.com/concerts/30913429-robag-wruhme-at-oval-space"
    ))
    assert "Die Vögel" in [artist.name for artist in event.artists]
