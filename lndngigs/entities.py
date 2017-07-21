from collections import namedtuple

Event = namedtuple("Event", ["link", "artists", "venue", "time"])
EventWithTags = namedtuple("EventWithTags", ["link", "artists", "venue", "time", "tags"])
