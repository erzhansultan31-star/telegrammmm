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
    """Ықшам мәзір — небәрі 5 батырма."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_set_cover"), callback_data="set_cover")
    kb.button(text=t(lang, "btn_set_author"), callback_data="set_author")
    kb.button(text=t(lang, "btn_search_music"), callback_data="search_music")
    kb.button(text=t(lang, "btn_change_lang"), callback_data="change_lang")
    kb.button(text=t(lang, "btn_reset"), callback_data="reset_profile")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def search_results_keyboard(lang: str, results: list) -> InlineKeyboardMarkup:
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
    kb.button(text=t(lang, "btn_apply_profile"), callback_data=f"apply_profile_{idx}")
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()
