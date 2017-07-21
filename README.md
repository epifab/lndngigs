# lndnGigs

_GIGS IN YOUR CITY_  



## Run the application

The application exposes a Slack slash command endpoint: https://api.slack.com/slash-commands.  
When the Slack app is properly installed and configured on your slack team, a slack bot will respond to `/gigs` commands.  

This is the default entrypoint of the application.

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
