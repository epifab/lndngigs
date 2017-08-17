from collections import namedtuple

Event = namedtuple("Event", ["link", "artists", "venue"])


class EventWithTags(namedtuple("EventWithTags", ["link", "artists", "venue", "tags"])):
    def to_dict(self):
        return {
            "link": self.link,
            "artists": self.artists,
            "venue": self.venue,
            "tags": self.tags
        }
