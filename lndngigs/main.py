import os
from flask import Flask, request

from lndngigs.integrations import EventListing, SongkickApi, LastFmApi, LastFmConfig, SlackBot, SlackConfig, get_logger

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
    logger = get_logger()

    slack_bot = SlackBot(
        logger=logger,
        config=SlackConfig(),
        event_listing=EventListing(
            songkick=SongkickApi(),
            lastfm=LastFmApi(LastFmConfig())
        )
    )

    app.run(
        host="0.0.0.0",
        port=int(os.getenv('PORT', 5000))
    )
