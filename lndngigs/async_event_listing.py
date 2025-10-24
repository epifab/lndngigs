import asyncio

from aiohttp import ClientSession

from lndngigs.entities import Venue
from lndngigs.event_listing import EventListingInterface, SongkickScraper
from lxml import html

async def fetch_url(url):
    async with ClientSession() as session:
        async with session.get(url) as response:
            return (await response.read()).decode("utf-8")


class AsyncEventListingLite(SongkickScraper, EventListingInterface):
    def __init__(self, logger, event_loop):
        self._logger = logger
        self._event_loop = event_loop

    async def scrape_event(self, events_date, url):
        return self.parse_event_page(self._logger, url, await fetch_url(url), events_date)

    async def scrape_event_listing_page(self, events_date, url):
        event_urls, page_urls = self.parse_event_listing_page(self._logger, url, await fetch_url(url))
        return await asyncio.gather(*[self.scrape_event(events_date, url) for url in event_urls]), page_urls

    async def scrape_venue_address(self, url):
        self._logger.debug("Scraping venue at {}".format(url))
        tree = html.fromstring(await fetch_url(url))
        return ", ".join(
            [
                element.text.strip()
                for element in tree.cssselect("p.venue-hcard span span")
                if element.text is not None and element.text.strip() != ""
            ][:3]
        )

    async def scrape_events(self, events_date, url):
        scraped_page_urls = set()
        discovered_page_urls = {url}
        all_events = []

        while discovered_page_urls:
            scraping_tasks = [self.scrape_event_listing_page(events_date, url) for url in discovered_page_urls]

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

        # Extract unique venue URLs
        unique_venue_urls = {
            event.venue.url
            for event in all_events
            if event.venue is not None
        }

        # Scrape all unique venues concurrently
        venue_scraping_tasks = [self.scrape_venue_address(url) for url in unique_venue_urls]
        venue_addresses = await asyncio.gather(*venue_scraping_tasks)

        # Create a mapping from venue URL to address
        venue_url_to_address = dict(zip(unique_venue_urls, venue_addresses))

        # Update all events with the scraped venue addresses
        all_events = [
            event._replace(
                venue=Venue(
                    url=event.venue.url,
                    name=event.venue.name,
                    address=venue_url_to_address[event.venue.url]
                )
            ) if event.venue is not None else event
            for event in all_events
        ]

        return all_events

    def get_events(self, location, events_date):
        yield from self._event_loop.run_until_complete(
            self.scrape_events(events_date, self.get_events_listing_url(location, events_date))
        )
