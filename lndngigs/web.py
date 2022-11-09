from flask import Flask, request, jsonify

from lndngigs.factories import *
from lndngigs.utils import Config, ValidationException


def build_app(logger, redis_client):
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Hello from lndnGigs!", 200

    @app.route("/gigs", defaults={"location": "london", "events_date": "today"})
    @app.route("/gigs/<location>/<events_date>", methods=['GET'])
    def gigs(location, events_date):
        if request.args.get("mode") == "nocache" or not redis_client:
            event_listing = get_event_listing_lite_no_cache(logger=logger)

        else:
            event_listing = get_event_listing_lite(
                logger=logger,
                redis_client=redis_client
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

    return app


if __name__ == 'lndngigs.web':
    config = Config()
    app = build_app(logger=get_logger(config.DEBUG), redis_client=get_redis_client(config))
