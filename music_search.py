# -*- coding: utf-8 -*-
"""
Музыка іздеу — Apple-дың ресми, ашық iTunes Search API арқылы.
Бұл API әннің атын, орындаушысын, мұқабасын және 30 секундтық
preview сілтемесін қайтарады. Толық ән файлын жүктемейді/таратпайды,
сондықтан авторлық құқыққа қайшы келмейді.

Құжаттама: https://performance-partners.apple.com/search-api
"""

import aiohttp

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


async def search_music(query: str, limit: int = 5) -> list:
    """Сұраныс бойынша тректер тізімін қайтарады.

    Әр элемент: {"title": str, "artist": str, "cover_url": str, "preview_url": str}
    """
    params = {"term": query, "media": "music", "limit": limit}
    async with aiohttp.ClientSession() as session:
        async with session.get(ITUNES_SEARCH_URL, params=params, timeout=10) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

    results = []
    for item in data.get("results", []):
        cover_url = item.get("artworkUrl100", "") or ""
        if cover_url:
            # Кішкентай 100x100 суретті үлкен 600x600-ге ауыстырамыз
            cover_url = cover_url.replace("100x100bb", "600x600bb")
        results.append({
            "title": item.get("trackName") or "—",
            "artist": item.get("artistName") or "—",
            "cover_url": cover_url,
            "preview_url": item.get("previewUrl") or "",
        })
    return results


async def download_bytes(url: str) -> bytes:
    """Берілген URL-ден bytes жүктейді (мұқаба немесе preview үшін)."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as resp:
            resp.raise_for_status()
            return await resp.read()
