import os

import redis
from flask import Flask, request

from lndngigs.factories import get_logger
from lndngigs.utils import Config, CommandMessagesQueue

app = Flask(__name__)


@app.route("/slack/gigs", methods=['POST'])
def slack_gigs():
    redis_client = redis.from_url(Config().REDIS_URL)

    logger.debug("Request keys: {}".format(request.form.keys()))

    queue = CommandMessagesQueue(redis_client=redis_client)
    queue.push({
        "text": "gigs {}".format(request.form["text"]),
        "user": request.form["user_name"],
        "channel": request.form["channel_id"],
    })

    return "Yo! I asked a friend about those gigs... stay tuned!"


if __name__ == '__main__':
    config = Config()
    logger = get_logger(config.DEBUG)
    app.run(
        host="0.0.0.0",
        port=int(os.getenv('PORT', 5000))
    )
