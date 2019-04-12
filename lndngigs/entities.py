from collections import namedtuple


class Event(namedtuple("Event", ["link", "artists", "venue", "date"])):
    def to_dict(self):
        return {
            "link": self.link,
            "artists": [artist.to_dict() for artist in self.artists],
            "venue": self.venue.to_dict() if self.venue else None,
            "date": self.date.strftime('%Y-%m-%d'),
        }


class Venue(namedtuple("Venue", ["url", "name", "address"])):
    def to_dict(self):
        return {
            "url": self.url,
            "name": self.name,
            "address": self.address
        }


class Artist(namedtuple("Artist", ["url", "name"])):
    def to_dict(self):
        return {
            "url": self.url,
            "name": self.name
        }


class ArtistWithMeta(namedtuple("ArtistWithMeta", ["url", "name", "tags", "image_url"])):
    def to_dict(self):
        return {
            "url": self.url,
            "name": self.name,
            "tags": self.tags,
            "image_url": self.image_url
        }
