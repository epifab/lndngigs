import asyncio

from aiohttp import ClientSession

from lndngigs.entities import EventWithTags
from lndngigs.event_listing import EventListingInterface, LastFmApi, SongkickScraper
from lndngigs.event_listingv1 import EventListing1


async def fetch(url, session):
    async with session.get(url) as response:
        return url, await response.read()


async def fetch_urls(callback, urls):
    async with ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]

        return [
            callback(url, response)
            for url, response in await asyncio.gather(*tasks)
        ]


class AsyncSongkickApi(SongkickScraper):
    def __init__(self, logger, event_loop):
        self._logger = logger
        self._event_loop = event_loop

    async def scrape_event_urls(self, url):
        scraped_page_urls = set()
        discovered_page_urls = {url}
        all_event_urls = []

        def event_listing_page_parser(url, content):
            return self.parse_event_listing_page(self._logger, url, content)

        while discovered_page_urls:
            # Scrape the discovered pages
            for page_event_urls, new_page_urls in await fetch_urls(event_listing_page_parser, discovered_page_urls):
                # Adds the discovered to the scraped set
                scraped_page_urls |= set(discovered_page_urls)
                discovered_page_urls = {
                    url for url in new_page_urls
                    if url not in scraped_page_urls
                    and "page=1" not in url  # This will prevent the first page from being scraped twice
                }
                all_event_urls += page_event_urls

        return all_event_urls

    async def get_async_events(self, location, events_date):
        def event_page_parser(url, content):
            return self.parse_event_page(self._logger, url, content)

        first_page_url = EventListing1.get_events_listing_url(location, events_date)
        event_urls = await self.scrape_event_urls(first_page_url)
        return await fetch_urls(event_page_parser, event_urls)


class EventListing2(EventListingInterface):
    def __init__(self, event_loop, songkick_api: AsyncSongkickApi, lastfm_api: LastFmApi):
        self._event_loop = event_loop
        self._songkick_api = songkick_api
        self._lastfm_api = lastfm_api

    async def async_get_events(self, location, events_date):
        return [
            EventWithTags(
                link=event.link,
                venue=event.venue,
                artists=event.artists,
                date=events_date,
                tags=[
                    tags
                    for tags_list in await asyncio.gather(*[
                        self._event_loop.run_in_executor(None, self._lastfm_api.artist_tags, artist)
                        for artist in event.artists
                    ])  # list of lists
                    for tags in tags_list
                ]
            )
            for event in await self._songkick_api.get_async_events(location, events_date)
        ]

    def get_events(self, location, events_date):
        return self._event_loop.run_until_complete(self.async_get_events(location, events_date))

    def parse_event_date(self, date_str):
        return self._songkick_api.parse_event_date(date_str)

    def parse_event_location(self, location):
        return self._songkick_api.parse_event_location(location)
