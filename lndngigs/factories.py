import asyncio
import logging
import sys

from redis.client import Redis

from lndngigs.event_listing import CachedEventListing, LastFmApi, EventListingInterface
from lndngigs.event_listingv3 import AsyncEventListing
from lndngigs.slack import SlackBot
from lndngigs.utils import Config


def get_logger(debug=False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO

    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setLevel(level)
    log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s:%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))

    logger = logging.getLogger('lndngigs')
    logger.setLevel(level)
    for handler in logger.handlers:
        logger.removeHandler(handler)
    logger.addHandler(log_handler)

    return logger


def get_event_listing(logger, lastfm_api_key, lastfm_api_secret) -> EventListingInterface:
    return AsyncEventListing(
        logger=logger,
        event_loop=asyncio.get_event_loop(),
        lastfm_api=LastFmApi(logger=logger, lastfm_api_key=lastfm_api_key, lastfm_api_secret=lastfm_api_secret),
    )


def get_slack_bot(logger, config: Config) -> SlackBot:
    return SlackBot(
        logger=logger,
        event_listing=get_event_listing(
            logger=logger,
            lastfm_api_key=config.LASTFM_API_KEY,
            lastfm_api_secret=config.LASTFM_API_SECRET
        ),
        slack_api_token=config.SLACK_API_TOKEN
    )
