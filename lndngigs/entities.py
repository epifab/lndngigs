from collections import namedtuple


class Event(namedtuple("Event", ["link", "artists", "venue", "date"])):
    def to_dict(self):
        return {
            "link": self.link,
            "artists": [artist.to_dict() for artist in self.artists],
            "venue": self.venue,
            "date": self.date.strftime('%Y-%m-%d'),
        }


class Artist(namedtuple("Artist", ["name", "tags", "image_url"])):
    def to_dict(self):
        return {
            "name": self.name,
            "tags": self.tags,
            "image_url": self.image_url
        }


class ArtistLite(namedtuple("ArtistLite", ["name"])):
    def to_dict(self):
        return {
            "name": self.name
        }
