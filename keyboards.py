# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from locales import t


def lang_keyboard() -> InlineKeyboardMarkup:
    """Тіл таңдау батырмалары."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang_ru")
    kb.button(text="🇰🇿 Қазақша", callback_data="lang_kz")
    kb.adjust(2)
    return kb.as_markup()


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Негізгі мәзір."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_send_photo"), callback_data="send_photo")
    kb.button(text=t(lang, "btn_add_name"), callback_data="add_name")
    kb.button(text=t(lang, "btn_add_author"), callback_data="add_author")
    kb.button(text=t(lang, "btn_filters"), callback_data="filters")
    kb.button(text=t(lang, "btn_resize"), callback_data="resize")
    kb.button(text=t(lang, "btn_preview"), callback_data="preview")
    kb.button(text=t(lang, "btn_download"), callback_data="download")
    kb.button(text=t(lang, "btn_restart"), callback_data="restart")
    kb.button(text=t(lang, "btn_change_lang"), callback_data="change_lang")
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


def filters_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Фильтр таңдау батырмалары."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "filter_bw"), callback_data="filter_bw")
    kb.button(text=t(lang, "filter_sepia"), callback_data="filter_sepia")
    kb.button(text=t(lang, "filter_blur"), callback_data="filter_blur")
    kb.button(text=t(lang, "filter_sharpen"), callback_data="filter_sharpen")
    kb.button(text=t(lang, "filter_none"), callback_data="filter_none")
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def resize_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Өлшем таңдау батырмалары."""
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "resize_small"), callback_data="resize_480")
    kb.button(text=t(lang, "resize_medium"), callback_data="resize_800")
    kb.button(text=t(lang, "resize_large"), callback_data="resize_1280")
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()


def back_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_back"), callback_data="back_to_menu")
    kb.adjust(1)
    return kb.as_markup()
