import argparse
from datetime import date

import sys

from lndngigs.integrations import get_logger, Config, get_slack_bot, parse_date


def run(location, events_date, channel):
    config = Config()
    logger = get_logger(config.DEBUG)

    logger.info("Posting events for {location} on {date} to {channel}".format(
        location=location,
        date=events_date,
        channel=channel
    ))

    bot = get_slack_bot(logger=logger, config=config)

    bot.post_events_command(
        location=location,
        events_date=events_date,
        channel=channel
    )

    logger.info("Events posted")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--location', dest='location', default='london')
    parser.add_argument('--date', dest='date', default=date.today(), type=parse_date)
    parser.add_argument('--channel', dest='channel', default="#lndngigs")

    args = parser.parse_args(sys.argv[1:])

    run(location=args.location, events_date=args.date, channel=args.channel)
