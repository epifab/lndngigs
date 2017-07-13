import os
import sys
from collections import namedtuple
from datetime import datetime, date, timedelta
import logging

import pylast
import robobrowser
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


class LastFmConfig:
    def __init__(self):
        self.LASTFM_API_KEY = os.environ["LASTFM_API_KEY"]
        self.LASTFM_API_SECRET = os.environ["LASTFM_API_SECRET"]


class LastFmApi:
    def __init__(self, config: LastFmConfig):
        self._lastfm = pylast.LastFMNetwork(
            api_key=config.LASTFM_API_KEY,
            api_secret=config.LASTFM_API_SECRET
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
    def __init__(self, songkick: SongkickApi, lastfm: LastFmApi):
        self._songkick = songkick
        self._lastfm = lastfm

    def get_events(self, location, events_date=date.today()):
        for event in self._songkick.get_events(location=location, events_date=events_date):
            yield EventWithTags(
                event=event,
                tags={
                    item
                    for sublist in (self._lastfm.artist_tags(artist_name) for artist_name in event.artists)
                    for item in sublist
                }
            )


class SlackException(Exception):
    pass


class SlackConfig:
    def __init__(self):
        self.SLACK_API_TOKEN = os.environ["SLACK_API_TOKEN"]


class SlackCommandError(Exception):
    pass


class SlackBot:
    def __init__(self, logger, config: SlackConfig, event_listing: EventListing):
        self._client = SlackClient(config.SLACK_API_TOKEN)
        if not self._client.rtm_connect():
            raise SlackException("Cannot connect to Slack")
        self._logger = logger
        self._event_listing = event_listing

    def event_message(self, event: Event, tags):
        return "> _Artists_: {artists}\n> _Venue_: {venue}\n> _Tags_: {tags}\n> {link}".format(
            artists=", ".join(event.artists),
            venue=event.venue,
            tags=", ".join(tags),
            link=event.link
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
            self.events_message(self._event_listing.get_events(location, events_date), location, events_date),
            channel
        )

    def run_command(self, message):
        command = message["text"].lower().split()
        usage_examples = ["gigs today", "gigs tomorrow", "gigs 20-03-2017"]
        location = "london"

        try:
            if command[0] == "gigs":
                try:
                    event_date = parse_date(command[1])
                except:
                    self._logger.info("Could not parse a date from `{}`".format(message["text"]))
                    raise SlackCommandError("When do you want to go gigging?")
                else:
                    self._logger.info("Sending events for {} in {} to `{}`".format(
                        event_date,
                        location,
                        message["user"]
                    ))
                    self.post_events_command(location, event_date, message["channel"])
            else:
                self._logger.info("Unkown command: `{}`".format(message["text"]))
                raise SlackCommandError("You wanna gig or not?")
        except SlackCommandError as e:
            self.send_message(
                "Hmm sorry didn't get that...\n{}\nUsage example:\n> {}".format(e, "\n> ".join(usage_examples)),
                channel=message["channel"]
            )

    def work(self):
        self._logger.info("Slack bot up and running!")
        try:
            while True:
                for message in self._client.rtm_read():
                    if message['type'] == 'message' and 'user' in message and 'bot_id' not in message:
                        self._logger.info("Received message from `{}`: `{}`".format(message["user"], message["text"]))
                        self.run_command(message)
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
