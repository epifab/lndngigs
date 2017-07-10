from datetime import date
import pytest

from lndngigs.integrations import LastFmConfig, LastFmApi, SongkickApi, EventListing


@pytest.fixture()
def lastfm_api():
    return LastFmApi(LastFmConfig())


@pytest.fixture()
def songkick_api():
    return SongkickApi()


@pytest.fixture()
def event_listing(songkick_api: SongkickApi, lastfm_api: LastFmApi):
    return EventListing(
        songkick=songkick_api,
        lastfm=lastfm_api
    )


def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10


def test_lastfm_api_with_unknown_artist(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("foobarbaz___123!")
    assert len(tags) == 0


def test_songkick_scraper(songkick_api: SongkickApi):
    events = songkick_api.get_events(location="london", events_date=date.today())
    assert len(list(events)) > 10


def test_event_with_tags(event_listing: EventListing):
    events_with_tags = event_listing.get_events("london", events_date=date.today())
    assert len(list(events_with_tags)) > 10
