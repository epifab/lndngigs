from collections import namedtuple

Event = namedtuple("Event", ["link", "artists", "venue"])
EventWithTags = namedtuple("EventWithTags", ["link", "artists", "venue", "tags"])
