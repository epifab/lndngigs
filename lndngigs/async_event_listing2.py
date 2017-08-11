import asyncio

from aiohttp import ClientSession
from lxml import html

from lndngigs.entities import EventWithTags
from lndngigs.event_listing import EventListingInterface, SongkickApi, LastFmApi


async def fetch_url(url):
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()


class AsyncEventListing2(EventListingInterface):
    parse_event_location = SongkickApi.parse_event_location
    parse_event_date = SongkickApi.parse_event_date

    def __init__(self, logger, event_loop, lastfm_api: LastFmApi):
        self._logger = logger
        self._event_loop = event_loop
        self._lastfm_api = lastfm_api

    async def scrape_event(self, url):
        content = await fetch_url(url)

        self._logger.debug("Scraping event at {}".format(url))
        tree = html.fromstring(content)

        artists = [
            element.text.strip()
            for element in tree.cssselect(".line-up a")
            if "href" in element.attrib and element.attrib["href"].startswith("/artists/")
        ]

        venue = ",".join([
            element.text.strip()
            for element in tree.cssselect(".location a")
            if element.attrib["href"].startswith("/venues/")
        ]) or "?"

        tags_tasks = [
            self._event_loop.run_in_executor(None, self._lastfm_api.artist_tags, artist)
            for artist in artists
        ]

        return EventWithTags(link=url, artists=artists, venue=venue, tags=[
                tags
                for tags_list in await asyncio.gather(*tags_tasks)  # list of lists
                for tags in tags_list
            ]
        )

    async def scrape_event_listing_page(self, url):
        content = await fetch_url(url)

        self._logger.debug("Scraping event listing at {}".format(url))
        tree = html.fromstring(content)

        event_urls = {
            "http://www.songkick.com{}".format(element.attrib["href"])
            for element in tree.cssselect(".event-listings a")
            if element.attrib["href"].startswith("/concerts/")
        }

        page_urls = {
            "http://www.songkick.com{}".format(element.attrib["href"])
            for element in tree.cssselect(".pagination a")
        }

        return await asyncio.gather(*[self.scrape_event(url) for url in event_urls]), page_urls


    async def scrape_events(self, url):
        scraped = set()
        discovered = {url}
        all_event_urls = []

        while discovered:
            # Scrape the discovered pages
            for events, page_urls in await asyncio.gather(*[self.scrape_event_listing_page(url) for url in discovered]):
                # Adds the discovered to the scraped set
                scraped |= set(discovered)
                discovered = {
                    url for url in page_urls
                    if url not in scraped
                    and "page=1" not in url  # This will prevent the first page from being scraped twice
                }
                all_event_urls += events

        return all_event_urls

    def get_events(self, location, events_date):
        yield from self._event_loop.run_until_complete(
            self.scrape_events(SongkickApi.get_events_listing_url(location, events_date))
        )
