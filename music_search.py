# -*- coding: utf-8 -*-
"""
Музыка іздеу — Apple-дың ресми, ашық iTunes Search API арқылы.
Бұл API әннің атын, орындаушысын, мұқабасын және 30 секундтық
preview сілтемесін қайтарады. Толық ән файлын жүктемейді/таратпайды,
сондықтан авторлық құқыққа қайшы келмейді.

Құжаттама: https://performance-partners.apple.com/search-api
"""

import logging

import aiohttp

logger = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

# iTunes серверлері User-Agent жоқ сұранысты кейде қабылдамайды/бөгейді
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TelegramMusicBot/1.0)"}


async def search_music(query: str, limit: int = 5) -> list:
    """Сұраныс бойынша тректер тізімін қайтарады.

    Әр элемент: {"title": str, "artist": str, "cover_url": str, "preview_url": str}
    """
    params = {"term": query, "media": "music", "limit": limit}
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
        async with session.get(ITUNES_SEARCH_URL, params=params) as resp:
            if resp.status != 200:
                logger.warning("iTunes API status %s: %s", resp.status, await resp.text())
                return []
            # МАҢЫЗДЫ: iTunes API "Content-Type: text/javascript" қайтарады,
            # ал aiohttp-тың resp.json() дефолты тек "application/json"
            # күтеді де ContentTypeError лақтырады. content_type=None осы
            # тексеруді өшіреді — дәл осы жерде іздеу "жұмыс істемей" тұрған.
            try:
                data = await resp.json(content_type=None)
            except Exception:
                logger.exception("iTunes JSON parse failed")
                return []

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
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(headers=_HEADERS, timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()
