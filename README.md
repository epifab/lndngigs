# lndnGigs


*This is an experimental project aimed to learn and experiment with different technologies.   
The use of this source code is intended for learning purposes only.*  


The application aggregates and caches events happening on a specific date in a specific location and exposes endpoints to retrieve them.


## Run using Docker

```bash
docker-compose up
```


## Technical notes

The scraping phase is made very fast thanks to the [asyncio library](https://docs.python.org/3/library/asyncio.html)

Events are shamelessly scraped from Songkick, and artists information are enhanced by using the Lastfm API 
and eventually cached in Redis.
