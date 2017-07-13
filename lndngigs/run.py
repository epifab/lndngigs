import argparse
from datetime import datetime, date

import sys

from lndngigs.integrations import EventListing, SongkickApi, LastFmApi, LastFmConfig, SlackBot, SlackConfig, get_logger


def main(logger, location, events_date, channel):
    logger.info("Posting events for {location} on {date} to {channel}".format(
        location=location,
        date=events_date,
        channel=channel
    ))

    event_listing = EventListing(SongkickApi(), LastFmApi(LastFmConfig()))

    bot = SlackBot(SlackConfig(), event_listing=event_listing)

    bot.post_events_command(
        location=location,
        events_date=events_date,
        channel=channel
    )

    logger.info("Events posted")


def parse_date(date_str):
    return datetime.strptime(date_str, '%d-%m-%Y').date()


if __name__ == '__main__':
    logger = get_logger()

    parser = argparse.ArgumentParser()

    parser.add_argument('--location', dest='location', default='london')
    parser.add_argument('--date', dest='date', default=date.today(), type=parse_date)
    parser.add_argument('--channel', dest='channel', default="#lndngigs")

    args = parser.parse_args(sys.argv[1:])

    main(logger, location=args.location, events_date=args.date, channel=args.channel)
