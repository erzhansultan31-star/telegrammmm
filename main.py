# -*- coding: utf-8 -*-
"""
Telegram фото-редактор боты.
Функциялар: тіл таңдау (RU/KZ), сурет жүктеу, атын/автор атын қосу,
фильтрлер (Ч/Б, сепия, блюр, резкость), өлшемін өзгерту, алдын ала қарау,
нәтижені жүктеу.

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
    filters_keyboard,
    resize_keyboard,
    back_keyboard,
)
from image_utils import (
    bytes_to_pil,
    pil_to_bytes,
    add_name,
    add_author,
    apply_filter,
    resize_image,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")   # мыс. https://your-app.onrender.com
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
        await target.message.edit_text(text, reply_markup=kb)
    elif isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


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
    await send_main_menu(callback, lang, edit=True)
    await callback.answer()


@dp.callback_query(F.data == "restart")
async def on_restart(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_data({"lang": lang})
    await state.set_state(None)
    await send_main_menu(callback, lang, edit=True)
    await callback.answer()


# ---------- Сурет жүктеу ----------

@dp.callback_query(F.data == "send_photo")
async def on_send_photo(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    await state.set_state(EditStates.waiting_photo)
    await callback.message.edit_text(t(lang, "ask_photo"))
    await callback.answer()


@dp.message(EditStates.waiting_photo, F.photo)
async def on_photo_received(message: Message, state: FSMContext):
    lang = await get_lang(state)
    photo = message.photo[-1]  # ең үлкен өлшемі
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    data = file_bytes.read()

    await state.update_data(original=data, current=data)
    await state.set_state(None)
    await message.answer(t(lang, "photo_received"), reply_markup=main_menu_keyboard(lang))


# ---------- Атын қосу ----------

@dp.callback_query(F.data == "add_name")
async def on_add_name(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    await state.set_state(EditStates.waiting_name)
    await callback.message.edit_text(t(lang, "ask_name"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_name, F.text)
async def on_name_entered(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    img = bytes_to_pil(data["current"])
    result_img = add_name(img, message.text.strip())
    result_bytes = pil_to_bytes(result_img)

    await state.update_data(current=result_bytes)
    await state.set_state(None)
    await message.answer(t(lang, "name_added"), reply_markup=main_menu_keyboard(lang))


# ---------- Автор атын қосу ----------

@dp.callback_query(F.data == "add_author")
async def on_add_author(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    await state.set_state(EditStates.waiting_author)
    await callback.message.edit_text(t(lang, "ask_author"), reply_markup=back_keyboard(lang))
    await callback.answer()


@dp.message(EditStates.waiting_author, F.text)
async def on_author_entered(message: Message, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    img = bytes_to_pil(data["current"])
    result_img = add_author(img, message.text.strip())
    result_bytes = pil_to_bytes(result_img)

    await state.update_data(current=result_bytes)
    await state.set_state(None)
    await message.answer(t(lang, "author_added"), reply_markup=main_menu_keyboard(lang))


# ---------- Фильтрлер ----------

@dp.callback_query(F.data == "filters")
async def on_filters_menu(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    await callback.message.edit_text(t(lang, "choose_filter"), reply_markup=filters_keyboard(lang))
    await callback.answer()


@dp.callback_query(F.data.startswith("filter_"))
async def on_filter_chosen(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    filter_name = callback.data.replace("filter_", "")  # bw / sepia / blur / sharpen / none

    img = bytes_to_pil(data["current"])
    result_img = apply_filter(img, filter_name)
    result_bytes = pil_to_bytes(result_img)

    await state.update_data(current=result_bytes)
    await callback.message.edit_text(t(lang, "filter_applied"), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


# ---------- Өлшемін өзгерту ----------

@dp.callback_query(F.data == "resize")
async def on_resize_menu(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    await callback.message.edit_text(t(lang, "ask_resize"), reply_markup=resize_keyboard(lang))
    await callback.answer()


@dp.callback_query(F.data.startswith("resize_"))
async def on_resize_chosen(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    max_side = int(callback.data.replace("resize_", ""))  # 480 / 800 / 1280

    img = bytes_to_pil(data["current"])
    result_img = resize_image(img, max_side)
    result_bytes = pil_to_bytes(result_img)

    await state.update_data(current=result_bytes)
    await callback.message.edit_text(t(lang, "resize_done"), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


# ---------- Алдын ала қарау / жүктеу ----------

@dp.callback_query(F.data == "preview")
async def on_preview(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    photo = BufferedInputFile(data["current"], filename="preview.jpg")
    await callback.message.answer_photo(photo)
    await send_main_menu(callback, lang)
    await callback.answer()


@dp.callback_query(F.data == "download")
async def on_download(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(state)
    data = await state.get_data()
    if "current" not in data:
        await callback.answer(t(lang, "no_photo_yet"), show_alert=True)
        return
    await callback.answer(t(lang, "sending_result"))
    doc = BufferedInputFile(data["current"], filename="result.jpg")
    await callback.message.answer_document(doc)
    await send_main_menu(callback, lang)


# ---------- Іске қосу (polling немесе webhook) ----------

async def on_startup(bot: Bot):
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
        logger.info("Webhook орнатылды: %s%s", WEBHOOK_URL, WEBHOOK_PATH)


def main():
    if WEBHOOK_URL:
        # ---- Render / кез келген веб-хостинг үшін webhook режимі ----
        dp.startup.register(on_startup)
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=PORT)
    else:
        # ---- Локалды тест үшін polling режимі ----
        async def _run():
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)

        asyncio.run(_run())


if __name__ == "__main__":
    main()
