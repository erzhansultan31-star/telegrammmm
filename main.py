# -*- coding: utf-8 -*-
"""
Telegram музыка-тег-редактор боты.
Функциялар: тіл таңдау (RU/KZ), ән (mp3) жүктеу, атын/авторын өзгерту,
мұқаба қою, тректі тыңдап көру/жүктеп алу, iTunes арқылы музыка іздеу
және табылған деректерді (ат/автор/мұқаба) өз әніне қолдану.

Іске қосу:
  - Локалды тест: python main.py          (polling режимі)
  - Render (webhook): WEBHOOK_URL env-ін орнатыңыз, платформа өзі
    PORT береді, скрипт автоматты webhook режиміне ауысады.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from locales import t
from states import EditStates
from keyboards import (
    lang_keyboard,
    main_menu_keyboard,
    back_keyboard,
    search_results_keyboard,
    track_detail_keyboard,
)
import audio_utils
import music_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN орнатылмаған! .env немесе Render Environment Variables ішіне қосыңыз.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ---------- Көмекші функциялар ----------

async def get_lang(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("lang", "ru")


async def send_main_menu(target, lang: str, edit: bool = False):
    text = t(lang, "main_menu")
    kb = main_menu_keyboard(lang)
    if edit and isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb)
        except Exception:
            await target.message.answer(text, reply_markup=kb)
    elif isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def require_audio(callback: CallbackQuery, state: FSMContext, lang: str) -> bytes | None:
    data = await state.get_data()
    if "audio" not in data:
        await callback.answer(t(lang, "no_audio_yet"), show_alert=True)
        return None
    return data["audio"]


# ---------- /start және тіл таңдау ----------

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(t("ru", "choose_lang"), reply_markup=lang_keyboard())


@dp.callback_query(F.data.in_(["lang_ru", "lang_kz"]))
async def on_lang_chosen(callback: CallbackQuery, state: FSMContext):
    lang = "ru" if callback.data == "lang_ru" else "kz"
    await state.update_data(lang=lang)
    await callback.message.edit_text(t(lang, "lang_set"))
    await send_main_menu(callback, lang)
    await callback.answer()


@dp.callback_query(F.data == "change_lang")
async def on_change_lang(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(t("ru", "choose_lang"), reply_markup=lang_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "back_to_menu")
async def on_back_to_menu(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(None)
    await send_main_menu(callback, lang, edit=True)
    await callback.answer()


@dp.callback_query(F.data == "restart")
async def on_restart(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_data({"lang": lang})
    await state.set_state(None)
    await send_main_menu(callback, lang, edit=True)
    await callback.answer()


# ---------- Ән (mp3) жүктеу ----------

@dp.callback_query(F.data == "send_audio")
async def on_send_audio(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(EditStates.waiting_audio)
    await callback.message.edit_text(t(lang, "ask_audio"))
    await callback.answer()


@dp.message(EditStates.waiting_audio, F.audio | F.document)
async def on_audio_received(message: Message, state: FSMContext):
    lang = await get_lang(state)
    file_obj = message.audio or message.document

    mime = (file_obj.mime_type or "")
    fname = (file_obj.file_name or "")
    if "audio" not in mime and not fname.lower().endswith(".mp3"):
        await message.answer(t(lang, "not_audio"))
        return

    file = await bot.get_file(file_obj.file_id)
    file_bytes = await bot.download_file(file.file_path)
    data = file_bytes.read()

    await state.update_data(audio=data)
    await state.set_state(None)
    await message.answer(t(lang, "audio_received"), reply_markup=main_menu_keyboard(lang))


# ---------- Атын өзгерту ----------

@dp.callback_query(F.data == "change_title")
async def on_change_title(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    if await require_audio(callback, state, lang) is None:
        return
    await state.set_state(EditStates.waiting_title)
    await callback.message.edit_text(t(lang, "ask_title"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_title, F.text)
async def on_title_entered(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    new_audio = audio_utils.set_title(data["audio"], message.text.strip())

    await state.update_data(audio=new_audio)
    await state.set_state(None)
    await message.answer(t(lang, "title_changed"), reply_markup=main_menu_keyboard(lang))


# ---------- Авторды өзгерту ----------

@dp.callback_query(F.data == "change_artist")
async def on_change_artist(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    if await require_audio(callback, state, lang) is None:
        return
    await state.set_state(EditStates.waiting_artist)
    await callback.message.edit_text(t(lang, "ask_artist"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_artist, F.text)
async def on_artist_entered(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    new_audio = audio_utils.set_artist(data["audio"], message.text.strip())

    await state.update_data(audio=new_audio)
    await state.set_state(None)
    await message.answer(t(lang, "artist_changed"), reply_markup=main_menu_keyboard(lang))


# ---------- Мұқаба қою ----------

@dp.callback_query(F.data == "set_cover")
async def on_set_cover(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    if await require_audio(callback, state, lang) is None:
        return
    await state.set_state(EditStates.waiting_cover_photo)
    await callback.message.edit_text(t(lang, "ask_cover"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_cover_photo, F.photo)
async def on_cover_photo_received(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    cover_bytes = file_bytes.read()

    new_audio = audio_utils.set_cover(data["audio"], cover_bytes)

    await state.update_data(audio=new_audio)
    await state.set_state(None)
    await message.answer(t(lang, "cover_changed"), reply_markup=main_menu_keyboard(lang))


# ---------- Ән туралы ақпарат ----------

@dp.callback_query(F.data == "track_info")
async def on_track_info(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    audio = await require_audio(callback, state, lang)
    if audio is None:
        return

    tags = audio_utils.get_tags(audio)
    text = t(
        lang, "current_info",
        title=tags["title"] or t(lang, "not_set"),
        artist=tags["artist"] or t(lang, "not_set"),
        cover=t(lang, "yes") if tags["has_cover"] else t(lang, "no"),
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard(lang))
    await callback.answer()


# ---------- Тыңдап көру / жүктеп алу ----------

@dp.callback_query(F.data == "preview")
async def on_preview(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    audio = await require_audio(callback, state, lang)
    if audio is None:
        return

    tags = audio_utils.get_tags(audio)
    cover = audio_utils.get_cover_bytes(audio)
    thumb = BufferedInputFile(cover, filename="cover.jpg") if cover else None

    audio_file = BufferedInputFile(audio, filename="preview.mp3")
    await callback.message.answer_audio(
        audio_file,
        title=tags["title"] or None,
        performer=tags["artist"] or None,
        thumbnail=thumb,
    )
    await send_main_menu(callback, lang)
    await callback.answer()


@dp.callback_query(F.data == "download")
async def on_download(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    audio = await require_audio(callback, state, lang)
    if audio is None:
        return

    await callback.answer(t(lang, "sending_result"))
    doc = BufferedInputFile(audio, filename="result.mp3")
    await callback.message.answer_document(doc)
    await send_main_menu(callback, lang)


# ---------- Музыка іздеу ----------

@dp.callback_query(F.data == "search_music")
async def on_search_music(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(EditStates.waiting_search_query)
    await callback.message.edit_text(t(lang, "ask_search_query"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_search_query, F.text)
async def on_search_query_entered(message: Message, state: FSMContext):
    lang = await get_lang(state)
    searching_msg = await message.answer(t(lang, "searching"))

    try:
        results = await music_search.search_music(message.text.strip(), limit=5)
    except Exception:
        logger.exception("Music search failed")
        results = []

    await state.update_data(search_results=results)
    await state.set_state(None)

    if not results:
        await searching_msg.edit_text(t(lang, "no_results"), reply_markup=back_keyboard(lang))
        return

    await searching_msg.edit_text(
        t(lang, "search_results"),
        reply_markup=search_results_keyboard(lang, results),
    )


@dp.callback_query(F.data.startswith("pick_track_"))
async def on_pick_track(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    idx = int(callback.data.replace("pick_track_", ""))
    results = data.get("search_results", [])

    if idx >= len(results):
        await callback.answer(t(lang, "error"), show_alert=True)
        return

    track = results[idx]
    text = t(lang, "track_info", title=track["title"], artist=track["artist"])
    kb = track_detail_keyboard(lang, idx)

    if track.get("cover_url"):
        try:
            cover_bytes = await music_search.download_bytes(track["cover_url"])
            photo = BufferedInputFile(cover_bytes, filename="cover.jpg")
            await callback.message.answer_photo(photo, caption=text, reply_markup=kb)
        except Exception:
            await callback.message.answer(text, reply_markup=kb)
    else:
        await callback.message.answer(text, reply_markup=kb)

    await callback.answer()


@dp.callback_query(F.data.startswith("apply_track_"))
async def on_apply_track(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()

    if "audio" not in data:
        await callback.answer(t(lang, "need_audio_first"), show_alert=True)
        return

    idx = int(callback.data.replace("apply_track_", ""))
    results = data.get("search_results", [])
    if idx >= len(results):
        await callback.answer(t(lang, "error"), show_alert=True)
        return

    track = results[idx]
    audio = data["audio"]

    audio = audio_utils.set_title(audio, track["title"])
    audio = audio_utils.set_artist(audio, track["artist"])

    if track.get("cover_url"):
        try:
            cover_bytes = await music_search.download_bytes(track["cover_url"])
            audio = audio_utils.set_cover(audio, cover_bytes)
        except Exception:
            logger.exception("Cover download/apply failed")

    await state.update_data(audio=audio)
    await callback.message.answer(t(lang, "applied_track"), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


# ---------- Іске қосу (polling немесе webhook) ----------

async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
        logger.info("Webhook орнатылды: %s%s", WEBHOOK_URL, WEBHOOK_PATH)


def main():
    if WEBHOOK_URL:
        dp.startup.register(on_startup)
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=PORT)
    else:
        async def _run():
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

        asyncio.run(_run())


if __name__ == "__main__":
    main()
