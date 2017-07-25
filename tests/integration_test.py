import pytest

from lndngigs.event_listing import EventListing, LastFmApi, SongkickApi
from lndngigs.utils import Config


@pytest.fixture()
def config():
    return Config()


@pytest.fixture()
def lastfm_api(config):
    return LastFmApi(lastfm_api_key=config.LASTFM_API_KEY, lastfm_api_secret=config.LASTFM_API_SECRET)


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
def test_songkick_scraper(songkick_api: SongkickApi):
    events = songkick_api.get_events(
        location=songkick_api.parse_event_location("london"),
        events_date=songkick_api.parse_event_date("monday")
    )
    assert len(list(events)) > 0


@pytest.mark.skip()
def test_event_with_tags(event_listing: EventListing):
    events_with_tags = event_listing.get_events(
        location=event_listing.parse_event_location("london"),
        events_date=event_listing.parse_event_date("monday")
    )
    assert len(list(events_with_tags)) > 0
