import asyncio
import aiohttp
import json

URLS_TO_CRAWL = [
    ("https://docs.python.org/3/tutorial/", 1),
    ("https://en.wikipedia.org/wiki/Web_crawler", 1),
    ("https://en.wikipedia.org/wiki/Search_engine", 1),
    ("https://fastapi.tiangolo.com/", 1),
    ("https://developer.mozilla.org/en-US/docs/Web/HTML", 1),
    ("https://news.ycombinator.com/", 1)
]

async def seed():
    print("=== Başlıyor: Seed Crawl ===")
    async with aiohttp.ClientSession() as session:
        for url, depth in URLS_TO_CRAWL:
            print(f"-> Crawling {url} (Depth: {depth})")
            try:
                async with session.post(
                    "http://localhost:3600/api/index",
                    json={"url": url, "depth": depth}
                ) as resp:
                    data = await resp.json()
                    print(f"   [OK] Job ID: {data.get('job_id')}")
            except Exception as e:
                print(f"   [HATA] {e}")
            await asyncio.sleep(1) # aralarda 1 sn bekle
    print("\n=== Tüm görevler kuyruğa eklendi. Dashboard'dan izleyebilirsiniz. ===")

if __name__ == "__main__":
    asyncio.run(seed())
