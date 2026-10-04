"""
Экран «О нас / Контакты».

Телефон — в тексте (кликабельный), плюс кнопки «Карта» и «Скопировать адрес».
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADDRESS, COMPANY_NAME, PHONE_DISPLAY
from keyboards.inline_kb import contacts_kb, menu_is
from handlers.utils import esc, render

router = Router(name="contacts")

CONTACTS_TEXT = (
    f"ℹ️ <b>{COMPANY_NAME}</b>\n\n"
    f"📞 <b>Телефон:</b>\n"
    f"<a href=\"tel:{PHONE_DISPLAY.replace(' ', '').replace('(', '').replace(')', '').replace('-', '')}\">{PHONE_DISPLAY}</a>\n\n"
    f"📍 <b>Адрес:</b>\n"
    f"{esc(ADDRESS)}\n\n"
    "Нажмите на номер, чтобы позвонить 👆"
)


@router.callback_query(menu_is("contacts"))
async def show_contacts(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(callback, CONTACTS_TEXT, contacts_kb())


@router.message(Command("contacts"), StateFilter("*"))
async def cmd_contacts(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render(message, CONTACTS_TEXT, contacts_kb())