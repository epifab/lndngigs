import asyncio
import logging
import sys

import redis
from redis import Redis

from lndngigs.event_listing import CachedEventListing, EventListingInterface
from lndngigs.async_event_listing import AsyncEventListingLite
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


def get_event_listing_lite(logger, redis_client: Redis) -> EventListingInterface:
    return CachedEventListing(
        logger=logger,
        event_listing=AsyncEventListingLite(
            logger=logger,
            event_loop=asyncio.get_event_loop()
        ),
        redis_client=redis_client,
        cache_key_prefix="events-lite"
    )


def get_event_listing_lite_no_cache(logger) -> EventListingInterface:
    return AsyncEventListingLite(
        logger=logger,
        event_loop=asyncio.get_event_loop()
    )


def get_redis_client(config: Config) -> Redis:
    return redis.from_url(config.REDIS_URL) if config.REDIS_URL else None
