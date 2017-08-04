from slackclient import SlackClient

from lndngigs.entities import EventWithTags
from lndngigs.utils import ValidationException
from lndngigs.event_listing import EventListingInterface


class SlackException(Exception):
    pass


class SlackCommandError(Exception):
    pass


class SlackBot:
    def __init__(self, logger, event_listing: EventListingInterface, slack_api_token):
        self._client = SlackClient(slack_api_token)
        if not self._client.rtm_connect():
            raise SlackException("Cannot connect to Slack")
        self._logger = logger
        self._event_listing = event_listing

    def event_message(self, event: EventWithTags):
        return "> _Artists_: {artists}\n> _Venue_: {venue}\n> _Tags_: {tags}\n> {link}".format(
            artists=", ".join(event.artists),
            venue=event.venue,
            tags=", ".join(event.tags),
            # this will prevent from display an event preview which is annoying when there are a lot of events
            link=event.link.replace("http://", "").replace("https://", "") if event else "?"
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
                events_date=events_date.strftime("%A, %d %B %Y")
            ),
            channel=channel
        )

        for event in self._event_listing.get_events(location=location, events_date=events_date):
            self.send_message(
                message=self.event_message(event),
                channel=channel
            )

    def run_command(self, text, user, channel):
        command = text.lower().split()
        usage_examples = ["gigs today", "gigs tomorrow", "gigs monday", "gigs 20-03-2017"]

        try:
            if command[0] == "gigs":
                # todo: take location as a (optional?) parameter
                location = self._event_listing.parse_event_location("london")

                try:
                    events_date = self._event_listing.parse_event_date(command[1])
                except ValidationException as e:
                    self._logger.info(str(e))
                    raise SlackCommandError(str(e))

                self._logger.info("Sending events for {} in {} to `{}`".format(
                    events_date,
                    "london",
                    user
                ))
                self.post_events_command(location, events_date, channel)
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

