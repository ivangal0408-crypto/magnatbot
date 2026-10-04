"""
Экран «О нас / Контакты».

Телефон — кликабельный (tel:), адрес — с кнопкой копирования и ссылкой на карту.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADDRESS, ARRIVAL_TIME, BOOKING_TIME, COMPANY_NAME, PHONE_DISPLAY
from keyboards.inline_kb import contacts_kb, menu_is
from handlers.utils import render

router = Router(name="contacts")

CONTACTS_TEXT = (
    f"ℹ️ <b>{COMPANY_NAME} — о нас</b>\n\n"
    "Автосервис полного цикла: диагностика подвески, двигателя, электрики, "
    "регламентное ТО, ремонт АКПП и ходовой.\n\n"
    f"📍 <b>Адрес:</b>\n<code>{ADDRESS}</code>\n"
    "<i>Нажмите «Скопировать адрес» или удерживайте текст адреса, чтобы скопировать.</i>\n\n"
    f"📞 <b>Телефон:</b> <a href=\"tel:{PHONE_DISPLAY.replace(' ', '')}\">{PHONE_DISPLAY}</a>\n"
    "Кнопка «Позвонить» ниже открывает набор номера на телефоне.\n\n"
    f"🕗 Режим работы: приём автомобилей с {BOOKING_TIME}, "
    f"подъёмники занимаем с {ARRIVAL_TIME}.\n"
    "🗓 Пн–Сб, по записи.\n\n"
    "Как добраться: въезд со стороны Меньковского тракта, парковка у ворот — "
    "ориентир синие ворота и вывеска «Магнат»."
)


@router.callback_query(menu_is("contacts"))
async def show_contacts(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(callback, CONTACTS_TEXT, contacts_kb())


@router.message(Command("contacts"), StateFilter("*"))
async def cmd_contacts(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render(message, CONTACTS_TEXT, contacts_kb())
