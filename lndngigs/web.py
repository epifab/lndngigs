import os

import redis
from flask import Flask, request, jsonify

from lndngigs.factories import get_logger, get_event_listing
from lndngigs.utils import Config, CommandMessagesQueue, ValidationException


def build_app(config, logger):
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Hello from lndnGigs!", 200

    @app.route("/gigs", defaults={"location": "london", "events_date": "today"})
    @app.route("/gigs/<location>/<events_date>", methods=['GET'])
    def gigs(location, events_date):
        event_listing = get_event_listing(
            logger=logger,
            redis_client=redis.from_url(config.REDIS_URL),
            lastfm_api_key=config.LASTFM_API_KEY,
            lastfm_api_secret=config.LASTFM_API_SECRET
        )
        try:
            parsed_location = event_listing.parse_event_location(location)
        except ValidationException as ex:
            return jsonify({
                "error": "Invalid location: {}".format(ex)
            }), 406

        try:
            parsed_events_date = event_listing.parse_event_date(events_date)
        except ValidationException as ex:
            return jsonify({
                "error": "Invalid date: {}".format(ex)
            }), 406

        events = [
            event.to_dict()
            for event in event_listing.get_events(location=parsed_location, events_date=parsed_events_date)
        ]

        return jsonify({"gigs": events}), 200

    @app.route("/slack/gigs", methods=['POST'])
    def slack_gigs():
        if "token" not in request.form or request.form["token"] != config.SLACK_VALIDATION_TOKEN:
            return "Invalid token", 403

        redis_client = redis.from_url(config.REDIS_URL)

        queue = CommandMessagesQueue(redis_client=redis_client)
        queue.push({
            "text": "gigs {}".format(request.form["text"]),
            "user": request.form["user_name"],
            "channel": "@{}".format(request.form["user_name"])  # request.form["channel_id"],
        })

        return "Yo! I asked a friend about those gigs... stay tuned!"

    return app


if __name__ == 'lndngigs.web':
    config = Config()
    app = build_app(config=config, logger=get_logger(config.DEBUG))
