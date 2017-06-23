import pytest

from lndngigs.main import LastFmConfig, LastFmApi


@pytest.fixture()
def lastfm_api():
    return LastFmApi(LastFmConfig())


def test_lastfm_api(lastfm_api: LastFmApi):
    tags = lastfm_api.artist_tags("radiohead")
    assert len(tags) == 10
