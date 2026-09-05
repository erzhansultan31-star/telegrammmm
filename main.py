# -*- coding: utf-8 -*-
"""
Telegram музыка-профиль боты.

Логикасы өте қарапайым:
  1) Пайдаланушы мұқаба мен автор атын БІР РЕТ орнатады (мәзірден).
  2) Содан кейін қандай уақытта mp3 жіберсе де, бот оны АВТОМАТТЫ
     түрде сол мұқаба+автормен өңдеп, дайын файлды бірден қайтарады.
     Ешқандай қосымша батырма басудың қажеті жоқ.

Деплой туралы МАҢЫЗДЫ ескерту:
  Render (тегін тариф) тек "Web Service" ұсынады, ол міндетті түрде
  $PORT портын ашуды талап етеді, әйтпесе "Timed Out" деп өшіріп,
  қайта-қайта рестарт жасайды — сол кезде бірнеше bot instance қатар
  polling жасап, Telegram "Conflict" қатесін қайтарады.

  Шешімі: webhook керек емес, ешқандай ақылы Background Worker де
  керек емес — біз polling-ды ЖӘНЕ жеңіл HTTP health-check серверін
  БІР процессте қатар іске қосамыз. Render порт ашылғанын көріп,
  сервисті "тірі" деп таниды да, енді өшірмейді/рестарт жасамайды.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BufferedInputFile
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
from storage import PostgresStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN орнатылмаған! Render Environment Variables ішіне қосыңыз.")

bot = Bot(token=BOT_TOKEN)

if DATABASE_URL:
    storage = PostgresStorage(DATABASE_URL)
    logger.info("Storage: Postgres (тұрақты, рестарт жасаса да сақталады)")
else:
    storage = MemoryStorage()
    logger.warning(
        "Storage: MemoryStorage (DATABASE_URL орнатылмаған) — "
        "сервер рестарт жасаса, барлық профильдер жоғалады!"
    )

dp = Dispatcher(storage=storage)


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


def _is_audio_message(message: Message) -> bool:
    file_obj = message.audio or message.document
    if not file_obj:
        return False
    mime = (file_obj.mime_type or "")
    fname = (file_obj.file_name or "")
    return "audio" in mime or fname.lower().endswith((".mp3", ".m4a", ".wav"))


# ---------- /start және тіл таңдау ----------

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    await state.set_state(None)
    if "lang" in data:
        await send_main_menu(message, lang)
    else:
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


@dp.callback_query(F.data == "reset_profile")
async def on_reset_profile(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.update_data(saved_cover=None, saved_author=None)
    await callback.answer(t(lang, "reset_done"), show_alert=True)
    await send_main_menu(callback, lang, edit=True)


# ---------- Мұқаба орнату (бір рет, тұрақты профиль) ----------

@dp.callback_query(F.data == "set_cover")
async def on_set_cover(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(EditStates.waiting_cover_photo)
    await callback.message.edit_text(t(lang, "ask_cover"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_cover_photo, F.photo)
async def on_cover_photo_received(message: Message, state: FSMContext):
    lang = await get_lang(state)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    cover_bytes = file_bytes.read()

    await state.update_data(saved_cover=cover_bytes)
    await state.set_state(None)
    await message.answer(t(lang, "cover_saved"), reply_markup=main_menu_keyboard(lang))


# ---------- Автор орнату (бір рет, тұрақты профиль) ----------

@dp.callback_query(F.data == "set_author")
async def on_set_author(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(EditStates.waiting_author_name)
    await callback.message.edit_text(t(lang, "ask_author"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_author_name, F.text)
async def on_author_name_received(message: Message, state: FSMContext):
    lang = await get_lang(state)
    await state.update_data(saved_author=message.text.strip())
    await state.set_state(None)
    await message.answer(t(lang, "author_saved"), reply_markup=main_menu_keyboard(lang))


# ---------- Музыка іздеу (табылған автор+мұқабаны профильге сақтайды) ----------

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


@dp.callback_query(F.data.startswith("apply_profile_"))
async def on_apply_profile(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    idx = int(callback.data.replace("apply_profile_", ""))
    results = data.get("search_results", [])
    if idx >= len(results):
        await callback.answer(t(lang, "error"), show_alert=True)
        return

    track = results[idx]
    update = {"saved_author": track["artist"]}

    if track.get("cover_url"):
        try:
            update["saved_cover"] = await music_search.download_bytes(track["cover_url"])
        except Exception:
            logger.exception("Cover download failed")

    await state.update_data(**update)
    await callback.message.answer(t(lang, "applied_profile"), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


# ---------- ГЛАВНОЕ: кез келген уақытта ән жіберсе — автоматты өңдеу ----------

@dp.message(F.audio | F.document)
async def on_any_audio_received(message: Message, state: FSMContext):
    lang = await get_lang(state)

    if not _is_audio_message(message):
        await message.answer(t(lang, "not_audio"))
        return

    # Пайдаланушы басқа диалогтың ортасында болса (мысалы автор атын
    # енгізуді күтіп тұрса), сол күйді тастап, тректі бәрібір өңдейміз.
    await state.set_state(None)

    data = await state.get_data()
    saved_cover = data.get("saved_cover")
    saved_author = data.get("saved_author")

    processing_msg = await message.answer(t(lang, "processing"))

    file_obj = message.audio or message.document
    file = await bot.get_file(file_obj.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_bytes = file_bytes.read()

    applied_anything = False
    try:
        if saved_author:
            audio_bytes = audio_utils.set_artist(audio_bytes, saved_author)
            applied_anything = True
        if saved_cover:
            audio_bytes = audio_utils.set_cover(audio_bytes, saved_cover)
            applied_anything = True
    except Exception:
        logger.exception("Audio processing failed")
        await processing_msg.edit_text(t(lang, "error"))
        return

    filename = file_obj.file_name or "result.mp3"
    caption = None if applied_anything else t(lang, "no_profile_yet")

    # Ендірілген тегтерді оқып аламыз (Telegram-да атын/авторын көрсету үшін)
    final_tags = audio_utils.get_tags(audio_bytes)

    # Мұқабаны Telegram-ның audio-плеерінде БІРДЕН көрсету үшін
    # бөлек кіші thumbnail жасаймыз (жай ID3 APIC-ті Telegram чатта
    # автоматты көрсетпейді, arnayı thumbnail керек).
    thumb = None
    if saved_cover:
        thumb_bytes = audio_utils.make_thumbnail(saved_cover)
        thumb = BufferedInputFile(thumb_bytes, filename="thumb.jpg")

    audio_input = BufferedInputFile(audio_bytes, filename=filename)

    await processing_msg.delete()
    await message.answer_audio(
        audio_input,
        title=final_tags.get("title"),
        performer=final_tags.get("artist"),
        thumbnail=thumb,
        caption=caption,
    )

    # Әрдайым мәзірге оралатын жол қалдырамыз — /start жазудың қажеті жоқ
    await send_main_menu(message, lang)


# ---------- Іске қосу: polling + жеңіл HTTP health-check сервер ----------
# Render "Web Service" ретінде $PORT ашуды талап етеді. Webhook та,
# ақылы Background Worker де керек емес — екеуін бір процессте қатар
# жүргіземіз, бот polling арқылы жұмыс істей береді.

async def start_health_server():
    app = web.Application()

    async def health(request):
        return web.Response(text="Bot is running")

    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Health-check сервері %s портында ашылды", PORT)


async def start_bot_polling():
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await storage.close()


async def main_async():
    await asyncio.gather(start_health_server(), start_bot_polling())


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
