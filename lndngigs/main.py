from lndngigs.integrations import EventListing, SongkickApi, LastFmApi, LastFmConfig, SlackBot, SlackConfig, get_logger

if __name__ == '__main__':
    SlackBot(
        logger=get_logger(),
        config=SlackConfig(),
        event_listing=EventListing(
            songkick=SongkickApi(),
            lastfm=LastFmApi(LastFmConfig())
        )
    ).work()
