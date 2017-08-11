import asyncio

from aiohttp import ClientSession
from lxml import html

from lndngigs.entities import Event, EventWithTags
from lndngigs.event_listing import EventListingInterface, SongkickApi, LastFmApi


async def fetch(url, session):
    async with session.get(url) as response:
        return url, await response.read()


async def fetch_urls(func, urls):
    async with ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]

        return [
            func(url, response)
            for url, response in await asyncio.gather(*tasks)
        ]


class AsyncSongkickApi(EventListingInterface):
    parse_event_location = SongkickApi.parse_event_location
    parse_event_date = SongkickApi.parse_event_date

    def __init__(self, logger, event_loop):
        self._logger = logger
        self._event_loop = event_loop

    def parse_event_page(self, url, content):
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

        return Event(link=url, artists=artists, venue=venue)

    def parse_event_listing_page(self, url, content):
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

        return event_urls, page_urls

    async def scrape_event_urls(self, url):
        scraped = set()
        discovered = {url}
        all_event_urls = []

        while discovered:
            # Scrape the discovered pages
            for event_urls, page_urls in await fetch_urls(self.parse_event_listing_page, discovered):
                # Adds the discovered to the scraped set
                scraped |= set(discovered)
                discovered = {
                    url for url in page_urls
                    if url not in scraped
                    and "page=1" not in url  # This will prevent the first page from being scraped twice
                }
                all_event_urls += event_urls

        return all_event_urls

    async def get_async_events(self, location, events_date):
        first_page_url = SongkickApi.get_events_listing_url(location, events_date)
        event_urls = await self.scrape_event_urls(first_page_url)
        return await fetch_urls(self.parse_event_page, event_urls)

    def get_events(self, location, events_date):
        yield from self._event_loop.run_until_complete(self.get_async_events(location, events_date))


class AsyncEventListing(EventListingInterface):
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
