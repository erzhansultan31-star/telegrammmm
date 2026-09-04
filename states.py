# -*- coding: utf-8 -*-
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    """Пайдаланушы диалогының күйлері."""
    waiting_photo = State()        # сурет күтілуде
    waiting_name = State()         # атын енгізуді күтуде
    waiting_author = State()       # автор атын енгізуді күтуде
    choosing_filter = State()      # фильтр таңдау
    choosing_resize = State()      # өлшем таңдау
