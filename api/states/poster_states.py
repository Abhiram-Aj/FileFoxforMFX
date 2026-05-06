"""
Aiogram v3 FSM state groups.
"""
from aiogram.fsm.state import State, StatesGroup


class PosterCreate(StatesGroup):
    waiting_photo    = State()
    waiting_caption  = State()
    waiting_button   = State()   # loop: add buttons one-by-one
    confirm          = State()


class PosterEdit(StatesGroup):
    choose_field     = State()
    editing_caption  = State()
    editing_photo    = State()
    editing_button   = State()
    confirm          = State()


class MultiCollect(StatesGroup):
    collecting       = State()


class ScheduleCreate(StatesGroup):
    waiting_datetime = State()
    waiting_channel  = State()
