import asyncio
import json
from datetime import timedelta, date

import pylast
import robobrowser
from redis import Redis
from aiohttp import ClientSession
from lxml import html

from lndngigs.entities import EventWithTags, Event
from lndngigs.utils import ValidationException, parse_date


class EventListingInterface:
    def get_events(self, location, events_date):
        raise NotImplementedError

    def parse_event_date(self, date_str):
        raise NotImplementedError

    def parse_event_location(self, location):
        raise NotImplementedError


class LastFmApi:
    def __init__(self, logger, lastfm_api_key, lastfm_api_secret):
        self._logger = logger
        self._lastfm = pylast.LastFMNetwork(
            api_key=lastfm_api_key,
            api_secret=lastfm_api_secret
        )

    def artist_tags(self, artist_name):
        try:
            self._logger.debug("Retrieving tags for `{}`".format(artist_name))
            return [str(tag.item) for tag in self._lastfm.get_artist(artist_name).get_top_tags(limit=10)]
        except pylast.WSError as ex:
            if ex.status == '6':
                self._logger.debug("Artist not found on lastfm: `{}`".format(artist_name))
                # Status returned when the artists couldn't be found
                # http://www.last.fm/api/errorcodes
                return []
            raise


class SongkickApi(EventListingInterface):
    LOCATIONS = {
        "london": "24426-uk-london",
        "berlin": "28443-germany-berlin",
        "amsterdam": "31366-netherlands-amsterdam",
        "barcelona": "28714-spain-barcelona",
    }
    USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:21.0.0) Gecko/20121011 Firefox/21.0.0"

    @classmethod
    def parse_event_location(cls, location: str):
        location = location.lower()
        if location not in cls.LOCATIONS.keys():
            raise ValidationException("`{}` is not a supported location. Try with: {}".format(
                location,
                ", ".join(cls.LOCATIONS)
            ))
        return cls.LOCATIONS[location]

    @classmethod
    def parse_event_date(cls, date_str):
        try:
            events_date = parse_date(date_str)
        except:
            raise ValidationException("Could not parse a date from `{}`".format(date_str))
        else:
            if events_date < date.today() or events_date > date.today() + timedelta(weeks=4):
                raise ValidationException("Could only lookup for events happening within 4 weeks from now")
            return events_date

    @classmethod
    def get_events_listing_url(cls, location, events_date):
        date_filters = \
            "&filters%5BminDate%5D={month}%2F{day}%2F{year}" \
            "&filters%5BmaxDate%5D={month}%2F{day}%2F{year}".format(
                year=events_date.year,
                month=events_date.month,
                day=events_date.day,
            )

        return "https://www.songkick.com/metro_areas/{location}?utf8=✓{date_filters}".format(
            location=location,
            date_filters=date_filters
        )

    def __init__(self):
        self._browser = robobrowser.RoboBrowser(
            parser="lxml",
            user_agent=self.USER_AGENT,
        )

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

            yield Event(
                link=event_link,
                artists=event_artists,
                venue=event_venue,
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


class EventListing(EventListingInterface):
    def __init__(self, songkick_api: SongkickApi, lastfm_api: LastFmApi):
        self._songkick_api = songkick_api
        self._lastfm_api = lastfm_api

    def get_events(self, location, events_date):
        # Retrieve events
        for event in self._songkick_api.get_events(location=location, events_date=events_date):
            yield EventWithTags(
                link=event.link,
                artists=event.artists,
                venue=event.venue,
                tags=[
                    item
                    for sublist in (self._lastfm_api.artist_tags(artist_name) for artist_name in event.artists)
                    for item in sublist
                ]
            )

    def parse_event_date(self, date_str):
        return self._songkick_api.parse_event_date(date_str)

    def parse_event_location(self, location):
        return self._songkick_api.parse_event_location(location)


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
                tags=await asyncio.gather(
                    self._event_loop.run_in_executor(None, self._lastfm_api.artist_tags, event.artists)
                )
            )
            for event in await self._songkick_api.get_async_events(location, events_date)
        ]

    def get_events(self, location, events_date):
        return self._event_loop.run_until_complete(self.async_get_events(location, events_date))

    def parse_event_date(self, date_str):
        return self._songkick_api.parse_event_date(date_str)

    def parse_event_location(self, location):
        return self._songkick_api.parse_event_location(location)


class CachedEventListing(EventListingInterface):
    def __init__(self, logger, event_listing: EventListingInterface, redis_client: Redis, cache_ttl=timedelta(days=1)):
        self._logger = logger
        self._event_listing = event_listing
        self._redis_client = redis_client
        self._cache_ttl = cache_ttl

    def get_cache_key_name(self, location, events_date):
        return "events:{}:{}".format(location, events_date)

    def get_cached_events(self, location, events_date):
        key_name = self.get_cache_key_name(location, events_date)

        if not self._redis_client.exists(key_name):
            self._logger.debug("Cache miss `{}`".format(key_name))
            return None

        self._logger.debug("Cache hit `{}`".format(key_name))

        event_json = self._redis_client.get(key_name).decode("utf-8")

        return [
            EventWithTags(
                link=event_with_tags["link"],
                artists=event_with_tags["artists"],
                venue=event_with_tags["venue"],
                tags=event_with_tags["tags"],
            )
            for event_with_tags in json.loads(event_json)
        ]

    def cache_events(self, location, events_date, events_with_tags):
        key_name = self.get_cache_key_name(location, events_date)
        self._redis_client.setex(
            name=key_name,
            value=json.dumps([
                {
                    "link": event.link,
                    "artists": event.artists,
                    "venue": event.venue,
                    "tags": event.tags
                }
                for event in events_with_tags
            ]).encode("utf-8"),
            time=self._cache_ttl
        )
        self._logger.debug("{} events cached: `{}`".format(len(events_with_tags), key_name))

    def get_events(self, location, events_date):
        events = self.get_cached_events(location, events_date)
        if events is not None:
            yield from events
        else:
            self._logger.debug("Retrieving events for {} in {}...".format(events_date, location))
            events = []
            for event in self._event_listing.get_events(location, events_date):
                yield event
                events.append(event)
            self.cache_events(location, events_date, events)

    def parse_event_date(self, date_str):
        return self._event_listing.parse_event_date(date_str)

    def parse_event_location(self, location):
        return self._event_listing.parse_event_location(location)
