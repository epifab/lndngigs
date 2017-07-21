import os

from flask import Flask, request

from lndngigs.integrations import get_logger, Config, get_slack_bot

app = Flask(__name__)


@app.route("/slack/gigs", methods=['POST'])
def slack_gigs():
    slack_bot.run_command(
        text="gigs {}".format(request.form["text"]),
        user=request.form["user_name"],
        channel=request.form["channel_id"],
    )
    return 'OK'


if __name__ == '__main__':
    config = Config()
    logger = get_logger(config.DEBUG)
    slack_bot = get_slack_bot(logger=logger, config=config)

    app.run(
        host="0.0.0.0",
        port=int(os.getenv('PORT', 5000))
    )
