import asyncio
from aiohttp.client import ClientSession


async def fetch_url(url):
    async with ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()


async def test(urls):
    yield from (await asyncio.gather(*[fetch_url(url) for url in urls]))
