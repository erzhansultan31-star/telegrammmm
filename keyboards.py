# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from locales import t


def lang_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang_ru")
    kb.button(text="🇰🇿 Қазақша", callback_data="lang_kz")
    kb.adjust(2)
    return kb.as_markup()


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_send_audio"), callback_data="send_audio")
    kb.button(text=t(lang, "btn_change_title"), callback_data="change_title")
    kb.button(text=t(lang, "btn_change_artist"), callback_data="change_artist")
    kb.button(text=t(lang, "btn_set_cover"), callback_data="set_cover")
    kb.button(text=t(lang, "btn_search_music"), callback_data="search_music")
    kb.button(text=t(lang, "btn_info"), callback_data="track_info")
    kb.button(text=t(lang, "btn_preview"), callback_data="preview")
    kb.button(text=t(lang, "btn_download"), callback_data="download")
    kb.button(text=t(lang, "btn_restart"), callback_data="restart")
    kb.button(text=t(lang, "btn_change_lang"), callback_data="change_lang")
    kb.adjust(2, 2, 2, 2, 1, 1)
    return kb.as_markup()


def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def search_results_keyboard(lang: str, results: list) -> InlineKeyboardMarkup:
    """Іздеу нәтижелерінің тізімі, әр трек — жеке батырма."""
    kb = InlineKeyboardBuilder()
    for idx, track in enumerate(results):
        label = f"{track['title']} — {track['artist']}"
        if len(label) > 60:
            label = label[:57] + "..."
        kb.button(text=label, callback_data=f"pick_track_{idx}")
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def track_detail_keyboard(lang: str, idx: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "apply_track"), callback_data=f"apply_track_{idx}")
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()
