from datetime import datetime
import pytest

from lndngigs.main import LastFmConfig, LastFmApi, SongkickApi, EventLister


@pytest.fixture()
def lastfm_api():
    return LastFmApi(LastFmConfig())


@pytest.fixture()
def songkick_api():
    return SongkickApi()


@pytest.fixture()
def event_lister(songkick_api: SongkickApi, lastfm_api: LastFmApi):
    return EventLister(
        songkick=songkick_api,
        lastfm=lastfm_api
    )


@pytest.mark.skip()
def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10


def test_lastfm_api_with_unknown_artist(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("foobarbaz___123!")
    assert len(tags) == 0


@pytest.mark.skip()
def test_songkick_scraper(songkick_api: SongkickApi):
    events = songkick_api.get_events(location="london", date=datetime.utcnow())
    assert len(list(events)) > 10


@pytest.mark.skip()
def test_event_with_tags(event_lister: EventLister):
    events_with_tags = event_lister.get_events("bristol")
    assert len(list(events_with_tags)) > 0
