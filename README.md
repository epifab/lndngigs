# lndnGigs

Hack day application to scrape events and aggregate useful information about bands playing in town.


## Run application using Docker

```bash
docker build -t lndngigs .

docker run \
 -e LASTFM_API_KEY=*** \
 -e LASTFM_API_SECRET=*** \
 -e SLACK_API_TOKEN=*** \
 lndngigs \
 --location bristol --channel @mychannel --date 01-01-2018
```
