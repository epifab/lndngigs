import robobrowser

from lndngigs.entities import EventWithTags
from lndngigs.event_listing import EventListingInterface, SongkickScraper, LastFmApi


class EventListing1(SongkickScraper, EventListingInterface):
    USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:21.0.0) Gecko/20121011 Firefox/21.0.0"

    def __init__(self, lastfm_api: LastFmApi):
        self._browser = robobrowser.RoboBrowser(
            parser="lxml",
            user_agent=self.USER_AGENT,
        )
        self._lastfm_api = lastfm_api

    def _scrape_page_events(self):
        for event in self._browser.select("ul.event-listings li"):
            event_summary_element = event.select_one(".summary a")
            if not event_summary_element:
                # Will skip every non-event item in the list
                continue

            event_link = "https://www.songkick.com{}".format(event_summary_element.get("href"))
            event_artists = [artist.strip() for artist in event_summary_element.select_one("strong").get_text().split(",")]

            try:
                event_venue = event.select_one(".venue-name a").get_text()
            except AttributeError:
                event_venue = "?"

            yield EventWithTags(
                link=event_link,
                artists=event_artists,
                venue=event_venue,
                tags=[
                    tag
                    for tags in (self._lastfm_api.artist_tags(artist_name) for artist_name in event_artists)
                    for tag in tags
                ]
            )

    def get_events(self, location, events_date):
        url = self.get_events_listing_url(location, events_date)

        self._browser.open(url)

        # Scrape the first page
        yield from self._scrape_page_events()

        while True:
            try:
                next_page_link = next(iter(self._browser.select(".pagination a.next_page")))
            except StopIteration:
                break
            else:
                self._browser.follow_link(next_page_link)
                yield from self._scrape_page_events()
