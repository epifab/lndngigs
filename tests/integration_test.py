from datetime import datetime
import pytest

from lndngigs.main import LastFmConfig, LastFmApi, SongkickApi


@pytest.fixture()
def lastfm_api():
    return LastFmApi(LastFmConfig())


@pytest.fixture()
def songkick_api():
    return SongkickApi()


def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10


def test_songkick_scraper(songkick_api: SongkickApi):
    events = songkick_api.get_events(location="24426-uk-london", date=datetime.utcnow(), limit=10)
    assert len(list(events)) > 10
