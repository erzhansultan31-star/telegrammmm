# -*- coding: utf-8 -*-
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    """Пайдаланушы диалогының күйлері."""
    waiting_audio = State()          # ән файлын күтуде
    waiting_title = State()          # жаңа атын енгізуді күтуде
    waiting_artist = State()         # жаңа автор атын енгізуді күтуде
    waiting_cover_photo = State()    # мұқаба суретін күтуде
    waiting_search_query = State()   # іздеу сөзін күтуде
