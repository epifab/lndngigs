import os
from collections import namedtuple
from datetime import datetime

import pylast
import robobrowser


class LastFmConfig:
    def __init__(self):
        self.LASTFM_API_KEY = os.environ["LASTFM_API_KEY"]
        self.LASTFM_API_SECRET = os.environ["LASTFM_API_SECRET"]


class LastFmApi:
    def __init__(self, config: LastFmConfig):
        self._lastfm = pylast.LastFMNetwork(
            api_key=config.LASTFM_API_KEY,
            api_secret=config.LASTFM_API_SECRET
        )

    def artist_tags(self, artist_name):
        return self._lastfm.get_artist(artist_name).get_top_tags(limit=10)


SongkickEvent = namedtuple("SongkickEvent", ["artists", "venue", "time"])


class SongkickApi:
    USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:21.0.0) Gecko/20121011 Firefox/21.0.0"

    def __init__(self):
        self._browser = robobrowser.RoboBrowser(
            parser="lxml",
            user_agent=self.USER_AGENT,
        )

    def _scrape_page_events(self):
        for event in self._browser.select("ul.event-listings li"):
            artist_info_element = event.select_one(".artists strong")
            if not artist_info_element:
                # Will skip every non-event item in the list
                continue

            venue_name_element = event.select_one(".venue-name a")
            venue_name = venue_name_element.get_text() if venue_name_element else "UNKNOWN"

            yield SongkickEvent(
                artists=artist_info_element.get_text(),
                time=event.select_one("time").get("datetime"),
                venue=venue_name
            )

    def get_events(self, location, date=datetime.utcnow(), limit=50):
        date_filters = \
            "&filters%5BminDate%5D={month}%2F{day}%2F{year}" \
            "&filters%5BmaxDate%5D={month}%2F{day}%2F{year}".format(
                year=date.year,
                month=date.month,
                day=date.day,
            )

        url = "https://www.songkick.com/metro_areas/{location}?utf8=✓{date_filters}".format(
            location=location,
            date_filters=date_filters
        )

        self._browser.open(url)

        # Scrape the first page
        yield from self._scrape_page_events()

        while True:
            try:
                next_page_link = next(iter(self._browser.select(".pagination a.next_page")))
                self._browser.follow_link(next_page_link)
                yield from self._scrape_page_events()
            except StopIteration:
                break


if __name__ == '__main__':
    print("Hello world")
