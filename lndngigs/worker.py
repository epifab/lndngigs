import redis

from lndngigs.integrations import get_slack_bot, Config, get_logger, CommandMessagesQueue


if __name__ == '__main__':
    config = Config()
    logger = get_logger(config.DEBUG)

    redis_client = redis.from_url(Config().REDIS_URL)

    slack_bot = get_slack_bot(logger=logger, redis_client=redis_client, config=config)

    queue = CommandMessagesQueue(redis_client=redis_client)

    for message in queue.messages():
        slack_bot.run_command(text=message["text"], user=message["user"], channel=message["channel"])
