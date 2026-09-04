# -*- coding: utf-8 -*-
"""
MP3 файлдарының ID3 тегтерін өңдеу: атын (TIT2), орындаушысын (TPE1)
және мұқабасын (APIC) оқу/жазу.

mutagen файл жолымен жұмыс істейді, сондықтан bytes-ты уақытша файлға
жазып, өзгертіп, қайта оқимыз.
"""

import io
import os
import tempfile
from typing import Optional

from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, APIC
from PIL import Image


# ---------- Көмекші: bytes <-> уақытша файл ----------

def _write_temp(data: bytes, suffix: str = ".mp3") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _read_and_cleanup(path: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data


def _load_id3(path: str) -> ID3:
    try:
        return ID3(path)
    except ID3NoHeaderError:
        return ID3()


# ---------- Тегтерді оқу ----------

def get_tags(data: bytes) -> dict:
    """Ағымдағы атын, авторын және мұқаба бар/жоғын қайтарады."""
    path = _write_temp(data)
    try:
        tags = _load_id3(path)
        title = str(tags["TIT2"].text[0]) if "TIT2" in tags else None
        artist = str(tags["TPE1"].text[0]) if "TPE1" in tags else None
        has_cover = any(key.startswith("APIC") for key in tags.keys())
        return {"title": title, "artist": artist, "has_cover": has_cover}
    finally:
        os.remove(path)


def get_cover_bytes(data: bytes) -> Optional[bytes]:
    """Ендірілген мұқаба суретін bytes түрінде қайтарады (жоқ болса None)."""
    path = _write_temp(data)
    try:
        tags = _load_id3(path)
        for key in tags.keys():
            if key.startswith("APIC"):
                return tags[key].data
        return None
    finally:
        os.remove(path)


# ---------- Тегтерді жазу ----------

def set_title(data: bytes, title: str) -> bytes:
    path = _write_temp(data)
    tags = _load_id3(path)
    tags["TIT2"] = TIT2(encoding=3, text=title)
    tags.save(path)
    return _read_and_cleanup(path)


def set_artist(data: bytes, artist: str) -> bytes:
    path = _write_temp(data)
    tags = _load_id3(path)
    tags["TPE1"] = TPE1(encoding=3, text=artist)
    tags.save(path)
    return _read_and_cleanup(path)


def set_cover(data: bytes, cover_bytes: bytes) -> bytes:
    """Мұқаба суретін JPEG-ке түрлендіріп (тым үлкен болмас үшін
    max 800px-ге дейін кішірейтіп), ID3 APIC фреймі ретінде ендіреді."""
    img = Image.open(io.BytesIO(cover_bytes)).convert("RGB")
    max_side = 800
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    jpeg_bytes = buf.getvalue()

    path = _write_temp(data)
    tags = _load_id3(path)
    tags.delall("APIC")
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=jpeg_bytes))
    tags.save(path)
    return _read_and_cleanup(path)
