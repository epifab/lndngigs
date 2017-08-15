import asyncio

from aiohttp import ClientSession

from lndngigs.entities import EventWithTags
from lndngigs.event_listing import EventListingInterface, LastFmApi, SongkickScraper


async def fetch_url(url):
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()


class EventListing3(SongkickScraper, EventListingInterface):
    def __init__(self, logger, event_loop, lastfm_api: LastFmApi):
        self._logger = logger
        self._event_loop = event_loop
        self._lastfm_api = lastfm_api

    async def scrape_event(self, url):
        event = self.parse_event_page(self._logger, url, await fetch_url(url))

        tags_tasks = [
            self._event_loop.run_in_executor(None, self._lastfm_api.artist_tags, artist)
            for artist in event.artists
        ]

        return EventWithTags(
            link=event.link,
            artists=event.artists,
            venue=event.venue,
            tags=[
                tags
                for tags_list in await asyncio.gather(*tags_tasks)  # list of lists
                for tags in tags_list
            ]
        )

    async def scrape_event_listing_page(self, url):
        event_urls, page_urls = self.parse_event_listing_page(self._logger, url, await fetch_url(url))
        return await asyncio.gather(*[self.scrape_event(url) for url in event_urls]), page_urls

    async def scrape_events(self, url):
        scraped_page_urls = set()
        discovered_page_urls = {url}
        all_events = []

        while discovered_page_urls:
            scraping_tasks = [self.scrape_event_listing_page(url) for url in discovered_page_urls]

            # Scrape the discovered pages
            for page_events, new_page_urls in await asyncio.gather(*scraping_tasks):
                # Adds the discovered to the scraped set
                scraped_page_urls |= set(discovered_page_urls)
                discovered_page_urls = {
                    url for url in new_page_urls
                    if url not in scraped_page_urls
                    and "page=1" not in url  # This will prevent the first page from being scraped twice
                }
                all_events += page_events

        return all_events

    def get_events(self, location, events_date):
        yield from self._event_loop.run_until_complete(
            self.scrape_events(self.get_events_listing_url(location, events_date))
        )
