import json
from datetime import timedelta

import pylast
import robobrowser

from redis import Redis

from lndngigs.entities import EventWithTags, Event


class EventListingInterface:
    def get_events(self, location, events_date):
        raise NotImplementedError


class LastFmApi:
    def __init__(self, lastfm_api_key, lastfm_api_secret):
        self._lastfm = pylast.LastFMNetwork(
            api_key=lastfm_api_key,
            api_secret=lastfm_api_secret
        )

    def artist_tags(self, artist_name):
        try:
            return [str(tag.item) for tag in self._lastfm.get_artist(artist_name).get_top_tags(limit=10)]
        except pylast.WSError as ex:
            if ex.status == '6':
                # Status returned when the artists couldn't be found
                # http://www.last.fm/api/errorcodes
                return []
            raise


class SongkickApi:
    LOCATIONS = {
        "london": "24426-uk-london",
        "bristol": "24521-uk-bristol",
        "porto": "31805-portugal-porto",
    }
    USER_AGENT = "Mozilla/5.0 (Windows NT 6.2; Win64; x64; rv:21.0.0) Gecko/20121011 Firefox/21.0.0"

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

            try:
                event_time = event.select_one("time").get("datetime")
            except AttributeError:
                event_time = "?"

            yield Event(
                link=event_link,
                artists=event_artists,
                venue=event_venue,
                time=event_time,
            )

    def get_events(self, location, events_date):
        if location not in self.LOCATIONS:
            raise ValueError("Unknown location {}".format(location))

        date_filters = \
            "&filters%5BminDate%5D={month}%2F{day}%2F{year}" \
            "&filters%5BmaxDate%5D={month}%2F{day}%2F{year}".format(
                year=events_date.year,
                month=events_date.month,
                day=events_date.day,
            )

        url = "https://www.songkick.com/metro_areas/{location}?utf8=✓{date_filters}".format(
            location=self.LOCATIONS[location],
            date_filters=date_filters
        )

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
                time=event.time,
                tags=[
                    item
                    for sublist in (self._lastfm_api.artist_tags(artist_name) for artist_name in event.artists)
                    for item in sublist
                ]
            )


class CachedEventListing(EventListingInterface):
    def __init__(self, logger, event_listing: EventListing, redis_client: Redis, cache_ttl=timedelta(days=3)):
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
                time=event_with_tags["time"],
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
                    "time": event.time,
                    "tags": tags
                }
                for event, tags in events_with_tags
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