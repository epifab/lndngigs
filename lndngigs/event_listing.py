import json
from datetime import timedelta, date

import pylast
from redis import Redis
from lxml import html

from lndngigs.entities import Event
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


class SongkickScraper:
    LOCATIONS = {
        "london": "24426-uk-london",
        "berlin": "28443-germany-berlin",
        "amsterdam": "31366-netherlands-amsterdam",
        "barcelona": "28714-spain-barcelona",
    }

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

    @staticmethod
    def parse_event_page(logger, url, content, events_date) -> Event:
        logger.debug("Scraping event at {}".format(url))
        tree = html.fromstring(content)

        artists = [
            element.text.strip()
            for element in tree.cssselect(".line-up a")
            if "href" in element.attrib and element.attrib["href"].startswith("/artists/")
        ]

        if not artists:
            # Sometimes the line-up is missing, let's try to get them from the summary
            artists = [
                element.text.strip()
                for element in tree.cssselect(".summary a")
                if "href" in element.attrib and element.attrib["href"].startswith("/artists/")
            ]

        venue = ",".join([
            element.text.strip()
            for element in tree.cssselect(".location a")
            if element.attrib["href"].startswith("/venues/")
        ]) or "?"

        return Event(link=url, artists=artists, venue=venue, date=events_date)

    @staticmethod
    def parse_event_listing_page(logger, url, content):
        logger.debug("Scraping event listing at {}".format(url))
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
            Event(
                link=event["link"],
                artists=event["artists"],
                venue=event["venue"],
                date=events_date
            )
            for event in json.loads(event_json)
        ]

    def cache_events(self, location, events_date, events_with_tags):
        key_name = self.get_cache_key_name(location, events_date)
        self._redis_client.setex(
            name=key_name,
            value=json.dumps([
                event.to_dict()
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
