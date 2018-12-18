from lndngigs.factories import get_slack_bot, get_logger, get_redis_client
from lndngigs.utils import Config, CommandMessagesQueue

if __name__ == '__main__':
    config = Config()
    logger = get_logger(config.DEBUG)

    redis_client = get_redis_client(config)

    slack_bot = get_slack_bot(logger=logger, config=config, redis_client=redis_client)

    queue = CommandMessagesQueue(redis_client=redis_client)

    for message in queue.messages():
        slack_bot.run_command(text=message["text"], user=message["user"], channel=message["channel"])
