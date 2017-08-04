import os

import redis
from flask import Flask, request

from lndngigs.factories import get_logger
from lndngigs.utils import Config, CommandMessagesQueue

app = Flask(__name__)

config = Config()
logger = get_logger(config.DEBUG)


@app.route("/slack/gigs", methods=['POST'])
def slack_gigs():
    if "token" not in request.form or request.form["token"] != config.SLACK_VALIDATION_TOKEN:
        return "Invalid token", 403

    redis_client = redis.from_url(config.REDIS_URL)

    logger.debug("Request keys: {}".format(", ".join(request.form.keys())))

    queue = CommandMessagesQueue(redis_client=redis_client)
    queue.push({
        "text": "gigs {}".format(request.form["text"]),
        "user": request.form["user_name"],
        "channel": "@{}".format(request.form["user_name"])  # request.form["channel_id"],
    })

    return "Yo! I asked a friend about those gigs... stay tuned!"


if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        port=int(os.getenv('PORT', 5000))
    )
