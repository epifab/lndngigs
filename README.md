# lndnGigs

_GIGS IN YOUR CITY_  


*This is an experimental project aimed to learn and experiment with different technologies.   
The use of this source code is intended for learning purposes only.*  


The application aggregates and caches events happening on a specific date in a specific location and exposes endpoints to retrieve them.


## Slack integration

_lndnGigs_ integrates with Slack by implementing a [slash command](https://api.slack.com/slash-commands) endpoint available at `/slack/gigs`.  
Further instruction about installing and configuring a Slack application can be found at https://api.slack.com/slack-apps  


## Run using Docker

```bash
docker-compose run \
 -e LASTFM_API_KEY=*** \
 -e LASTFM_API_SECRET=*** \
 -e SLACK_API_TOKEN=*** \
 lndngigs
```

You might want to just run a one-off command to post the list of events to a specific slack channel.

```bash
docker-compose run \
 -e LASTFM_API_KEY=*** \
 -e LASTFM_API_SECRET=*** \
 -e SLACK_API_TOKEN=*** \
 --entrypoint "python -m lndngigs.run"
 lndngigs --channel=*** --location=*** --date=***
```

Ultimately, to run the tests:

```bash
docker-compose run --entrypoint pytest lndngigs
```
