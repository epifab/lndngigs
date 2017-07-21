import json
import os
import sys
from collections import namedtuple
from datetime import datetime, date, timedelta
import logging

import pylast
import redis
import robobrowser
from redis.client import Redis
from slackclient import SlackClient


Event = namedtuple("Event", ["link", "artists", "venue", "time"])
EventWithTags = namedtuple("EventWithTags", ["event", "tags"])


def parse_date(date_str):
    if date_str.lower() == 'today':
        return date.today()
    elif date_str.lower() == 'tomorrow':
        return date.today() + timedelta(days=1)
    else:
        return datetime.strptime(date_str, '%d-%m-%Y').date()


class Config:
    def get(self, key, **kwargs):
        if not key in os.environ:
            if "default" not in kwargs:
                raise Exception("Environment variable '{}' is missing".format(key))
            else:
                return kwargs["default"]
        try:
            return kwargs["convert"](os.environ[key]) if "convert" in kwargs else os.environ[key]
        except:
            raise Exception("Variable '{}' is invalid".format(key))

    def __init__(self):
        self.LASTFM_API_KEY = self.get("LASTFM_API_KEY")
        self.LASTFM_API_SECRET = self.get("LASTFM_API_SECRET")
        self.SLACK_API_TOKEN = self.get("SLACK_API_TOKEN")
        self.REDIS_URL = self.get("REDIS_URL", default=None)


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

    def get_events(self, location, events_date=date.today()):
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


class EventListing:
    def __init__(self, songkick_api: SongkickApi, lastfm_api: LastFmApi):
        self._songkick_api = songkick_api
        self._lastfm_api = lastfm_api

    def get_events(self, location, events_date):
        # Retrieve events
        for event in self._songkick_api.get_events(location=location, events_date=events_date):
            yield EventWithTags(
                event=event,
                tags={
                    item
                    for sublist in (self._lastfm_api.artist_tags(artist_name) for artist_name in event.artists)
                    for item in sublist
                }
            )


class CachedEventListing:
    def __init__(self, event_listing: EventListing, redis_client: Redis, cache_ttl=timedelta(days=3)):
        self._event_listing = event_listing
        self._redis_client = redis_client
        self._cache_ttl = cache_ttl

    def get_cache_key_name(self, location, events_date):
        return "events:{}:{}".format(location, events_date)

    def get_cached_events(self, location, events_date):
        key_name = self.get_cache_key_name(location, events_date)

        if not self._redis_client.exists(key_name):
            return None

        event_json = self._redis_client.get(key_name).decode("utf-8")

        return [
            EventWithTags(
                event=Event(
                    link=event_with_tags["link"],
                    artists=event_with_tags["artists"],
                    venue=event_with_tags["venue"],
                    time=event_with_tags["time"]
                ),
                tags=event_with_tags["tags"]
            )
            for event_with_tags in json.loads(event_json)
        ]

    def cache_events(self, location, events_date, events_with_tags):
        self._redis_client.setex(
            name=self.get_cache_key_name(location, events_date),
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

    def get_events(self, location, events_date):
        events = self.get_cached_events(location, events_date)
        if events is not None:
            yield from events
        else:
            events = []
            for event in self._event_listing.get_events(location, events_date):
                yield event
                events.append(event)
            self.cache_events(location, events_date, events)


class SlackException(Exception):
    pass


class SlackCommandError(Exception):
    pass


class SlackBot:
    def __init__(self, logger, event_listing: EventListing, slack_api_token):
        self._client = SlackClient(slack_api_token)
        if not self._client.rtm_connect():
            raise SlackException("Cannot connect to Slack")
        self._logger = logger
        self._event_listing = event_listing

    def event_message(self, event: Event, tags):
        return "> _Artists_: {artists}\n> _Venue_: {venue}\n> _Tags_: {tags}\n> {link}".format(
            artists=", ".join(event.artists),
            venue=event.venue,
            tags=", ".join(tags),
            # this will prevent from display an event preview which is annoying when there are a lot of events
            link=event.link.replace("http://", "").replace("https://", "") if event else "?"
        )

    def events_message(self, events_with_tags, location, events_date):
        return "*Gigs in _{location}_ on _{events_date}_*\n\n{gigs}".format(
            location=location,
            events_date=events_date,
            gigs="\n\n".join(self.event_message(event, tags) for event, tags in events_with_tags)
        )

    def send_message(self, message, channel):
        results = self._client.api_call(
            "chat.postMessage",
            channel=channel,
            text=message,
            as_user=True
        )
        if not results['ok']:
            raise SlackException("Unable to post a message to slack: {}".format(results['error']))

    def post_events_command(self, location, events_date, channel):
        self.send_message(
            message="*Gigs in _{location}_ on _{events_date}_*".format(
                location=location,
                events_date=events_date
            ),
            channel=channel
        )

        for event, tags in self._event_listing.get_events(location=location, events_date=events_date):
            self.send_message(
                message=self.event_message(event, tags),
                channel=channel
            )

    def run_command(self, text, user, channel):
        command = text.lower().split()
        usage_examples = ["gigs today", "gigs tomorrow", "gigs 20-03-2017"]
        location = "london"

        try:
            if command[0] == "gigs":
                try:
                    event_date = parse_date(command[1])
                except:
                    self._logger.info("Could not parse a date from `{}`".format(text))
                    raise SlackCommandError("When do you want to go gigging?")
                else:
                    self._logger.info("Sending events for {} in {} to `{}`".format(
                        event_date,
                        location,
                        user
                    ))
                    self.post_events_command(location, event_date, channel)
            else:
                self._logger.info("Unkown command: `{}`".format(text))
                raise SlackCommandError("You wanna gig or not?")
        except SlackCommandError as e:
            self.send_message(
                "Hmm sorry didn't get that...\n{}\nUsage example:\n> {}".format(e, "\n> ".join(usage_examples)),
                channel=channel
            )

    def work(self):
        self._logger.info("Slack bot up and running!")
        try:
            while True:
                for message in self._client.rtm_read():
                    if message['type'] == 'message' and 'user' in message and 'bot_id' not in message:
                        self._logger.info("Received message from `{}`: `{}`".format(message["user"], message["text"]))
                        self.run_command(
                            text=message["text"],
                            user=message["user"],
                            channel=message["channel"]
                        )
        finally:
            self._logger.info("Slack bot going to sleep")


def get_logger(level=logging.INFO):
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setLevel(level)
    log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s:%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

    logger = logging.getLogger('lndngigs')
    logger.setLevel(level)
    for handler in logger.handlers:
        logger.removeHandler(handler)
    logger.addHandler(log_handler)

    return logger


def get_event_listing(lastfm_api_key, lastfm_api_secret, redis_url):
    event_listing = EventListing(
        lastfm_api=LastFmApi(lastfm_api_key=lastfm_api_key, lastfm_api_secret=lastfm_api_secret),
        songkick_api= SongkickApi(),
    )
    if redis_url:
        event_listing = CachedEventListing(
            event_listing=event_listing,
            redis_client=redis.from_url(redis_url)
        )
    return event_listing


def get_slack_bot(logger, config: Config):
    return SlackBot(
        logger=logger,
        event_listing=get_event_listing(
            lastfm_api_key=config.LASTFM_API_KEY,
            lastfm_api_secret=config.LASTFM_API_SECRET,
            redis_url=config.REDIS_URL,
        ),
        slack_api_token=config.SLACK_API_TOKEN
    )
