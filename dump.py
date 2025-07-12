import os
import aiohttp
import aiofiles
import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

visited_pages = set()
visited_assets = set()

base_url = input("Enter website URL (include https://): ").strip()
domain = urlparse(base_url).netloc
root_folder = f"dump_{domain.replace('.', '_')}"
sem = asyncio.Semaphore(10)  # limit concurrency

def to_path_from_url(url):
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/") or not os.path.basename(path):
        path = os.path.join(path, "index.html")
    elif "." not in os.path.basename(path):
        path = path + "/index.html"
    return os.path.join(root_folder, path.lstrip("/"))

async def save_asset(session, asset_url):
    if asset_url in visited_assets:
        return
    visited_assets.add(asset_url)
    try:
        async with sem:
            async with session.get(asset_url, timeout=10) as response:
                if response.status != 200:
                    return
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    return
                parsed = urlparse(asset_url)
                save_path = os.path.join(root_folder, parsed.path.lstrip("/"))
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                content = await response.read()
                async with aiofiles.open(save_path, "wb") as f:
                    await f.write(content)
                print(f"[Asset] ✅ {asset_url}")
    except Exception as e:
        print(f"[Asset] ❌ {asset_url} - {e}")

async def get_internal_links(soup, page_url):
    links = set()
    for a in soup.find_all("a"):
        if a.has_attr("href"):
            full_url = urljoin(page_url, a["href"])
            parsed = urlparse(full_url)
            if parsed.netloc == domain and not parsed.scheme.startswith("mailto"):
                links.add(full_url)
    return links

async def dump_page_recursive(session, page_url):
    if page_url in visited_pages:
        return
    visited_pages.add(page_url)

    try:
        async with sem:
            async with session.get(page_url, timeout=10) as res:
                if res.status != 200:
                    print(f"[Page] ❌ {page_url} - Status {res.status}")
                    return
                text = await res.text()
                soup = BeautifulSoup(text, "html.parser")

        # Go deeper first
        links = await get_internal_links(soup, page_url)
        await asyncio.gather(*(dump_page_recursive(session, link) for link in links))

        # Then save this page
        save_path = to_path_from_url(page_url)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        async with aiofiles.open(save_path, "w", encoding="utf-8") as f:
            await f.write(text)
        print(f"[Page] ✅ {page_url}")

        # Download page assets
        asset_tags = soup.find_all(["script", "link", "img", "source", "video", "audio", "iframe"])
        tasks = []
        for tag in asset_tags:
            attr = "href" if tag.name == "link" else "src"
            if tag.has_attr(attr):
                asset_url = urljoin(page_url, tag[attr])
                tasks.append(save_asset(session, asset_url))
        await asyncio.gather(*tasks)

    except Exception as e:
        print(f"[Page] ❌ {page_url} - {e}")

async def main():
    async with aiohttp.ClientSession() as session:
        await dump_page_recursive(session, base_url)
        print("\n🎉 Finished. Dumped to:", root_folder)

asyncio.run(main())
