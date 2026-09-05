# -*- coding: utf-8 -*-
"""
Aiogram FSM деректерін (тіл, сақталған мұқаба, автор т.б.) жадыда емес,
сыртқы Postgres базасында сақтайтын storage. Осының арқасында сервер
рестарт жасаса да (Render redeploy, sleep/wake) пайдаланушылардың
профилі жоғалмайды.

Тегін Postgres алу үшін: Neon (neon.tech) немесе Supabase (supabase.com)
— екеуі де тегін тарифте байланыс жолын (connection string) береді,
соны DATABASE_URL ретінде қойса болды.
"""

import base64
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs, urlunparse

import asyncpg
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

logger = logging.getLogger(__name__)


def _prepare_dsn(dsn: str):
    """asyncpg 'sslmode' query параметрін түсінбейді, сондықтан оны
    алып тастап, орнына ssl='require' ретінде береміз (Neon/Supabase
    әдетте sslmode=require қосылған сілтеме береді)."""
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    sslmode = query.pop("sslmode", None)
    new_query = "&".join(f"{k}={v[0]}" for k, v in query.items())
    clean_dsn = urlunparse(parsed._replace(query=new_query))
    ssl_arg = "require" if sslmode else None
    return clean_dsn, ssl_arg


def _json_default(obj: Any):
    """bytes-ты JSON-ға сыйдыру үшін base64-ке айналдырады."""
    if isinstance(obj, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(obj)).decode("ascii")}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_object_hook(d: Dict[str, Any]):
    if "__bytes__" in d:
        return base64.b64decode(d["__bytes__"])
    return d


class PostgresStorage(BaseStorage):
    """DATABASE_URL арқылы Postgres-ке қосылатын, кесте автоматты
    жасалатын, аса қарапайым FSM storage."""

    def __init__(self, dsn: str):
        self._dsn, self._ssl = _prepare_dsn(dsn)
        self._pool: Optional[asyncpg.pool.Pool] = None

    async def _ensure_pool(self) -> asyncpg.pool.Pool:
        if self._pool is None:
            kwargs = {"dsn": self._dsn, "min_size": 1, "max_size": 5}
            if self._ssl:
                kwargs["ssl"] = self._ssl
            self._pool = await asyncpg.create_pool(**kwargs)
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fsm_storage (
                        storage_key TEXT PRIMARY KEY,
                        state TEXT,
                        data TEXT
                    )
                    """
                )
            logger.info("Postgres storage дайын (кесте тексерілді/жасалды)")
        return self._pool

    @staticmethod
    def _key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}"

    async def set_state(self, key: StorageKey, state=None) -> None:
        pool = await self._ensure_pool()
        state_str = state.state if isinstance(state, State) else state
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO fsm_storage (storage_key, state) VALUES ($1, $2)
                ON CONFLICT (storage_key) DO UPDATE SET state = EXCLUDED.state
                """,
                self._key(key), state_str,
            )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM fsm_storage WHERE storage_key = $1", self._key(key)
            )
        return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        pool = await self._ensure_pool()
        encoded = json.dumps(data, default=_json_default)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO fsm_storage (storage_key, data) VALUES ($1, $2)
                ON CONFLICT (storage_key) DO UPDATE SET data = EXCLUDED.data
                """,
                self._key(key), encoded,
            )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM fsm_storage WHERE storage_key = $1", self._key(key)
            )
        if not row or not row["data"]:
            return {}
        return json.loads(row["data"], object_hook=_json_object_hook)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
