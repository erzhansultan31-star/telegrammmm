# -*- coding: utf-8 -*-
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    """Пайдаланушы диалогының күйлері."""
    waiting_cover_photo = State()    # мұқаба суретін күтуде
    waiting_author_name = State()    # автор атын күтуде
    waiting_search_query = State()   # іздеу сөзін күтуде
