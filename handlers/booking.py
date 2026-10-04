"""
Запись на диагностику.

Сценарий (FSM): дата (динамические кнопки: 3, 4, 5, 6 дней от текущей) →
время (строго 08:00, прибытие в 07:00) → подтверждение → сохранение в БД +
уведомление администратору в Telegram и письмом через EmailJS.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADDRESS, ARRIVAL_TIME, BOOKING_TIME
from database.db import (
    create_appointment,
    get_last_car,
    get_or_create_user,
    is_slot_taken,
)
from handlers.main_menu import MENU_TEXT
from handlers.utils import esc, render
from keyboards.inline_kb import (
    confirm_is,
    confirm_kb,
    date_is,
    dates_kb,
    done_kb,
    home_kb,
    menu_is,
    parse_iso_date,
    payload_value,
    time_is,
    time_kb,
)
from keyboards.reply_kb import is_cancel
from services.email_service import notify_admins

router = Router(name="booking")


class BookingStates(StatesGroup):
    date = State()
    time = State()
    confirm = State()


DATE_PROMPT = (
    "📅 <b>Запись на диагностику — шаг 1 из 2</b>\n\n"
    "Выберите дату. Свободные окна на ближайшие дни:\n"
    f"приём автомобилей строго в {BOOKING_TIME}.\n\n"
    "Если нужной даты нет — напишите в чат, согласуем отдельно."
)


def _time_prompt(date_label: str) -> str:
    return (
        f"📅 Дата: <b>{date_label}</b>\n\n"
        "🕗 <b>Запись на диагностику — шаг 2 из 2</b>\n\n"
        f"Время приёма: <b>{BOOKING_TIME}</b>.\n"
        f"⚠️ Приезжайте, пожалуйста, к <b>{ARRIVAL_TIME}</b> — в {BOOKING_TIME} "
        "подъёмник уже занят, и мы рискуем потерять ваше место в очереди."
    )


def _confirm_text(brand: str | None, regimen: str | None, date_label: str, time: str) -> str:
    lines = [
        "✅ <b>Проверьте запись</b>",
        "",
    ]
    if brand:
        lines.append(f"🚗 Автомобиль: <b>{esc(brand)}</b>")
    if regimen:
        lines.append(f"🔧 Цель визита: <b>{esc(regimen)} / диагностика</b>")
    else:
        lines.append("🔧 Цель визита: <b>диагностика</b>")
    lines += [
        "",
        f"📅 Дата: <b>{esc(date_label)}</b>",
        f"🕗 Время приёма: <b>{esc(time)}</b>",
        f"⏰ Прибытие: <b>{ARRIVAL_TIME}</b>",
        "",
        "Нажмите «Подтвердить» — отправим заявку мастеру-приёмщику.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Вход в сценарий
# ---------------------------------------------------------------------------
async def start_booking(
    target: Message | CallbackQuery,
    state: FSMContext,
    brand: str | None = None,
    regimen: str | None = None,
) -> None:
    """Открывает выбор даты (можно передать марку и регламент из калькулятора)."""
    await state.clear()

    user_id = None
    if target.from_user is not None:
        user = await get_or_create_user(
            target.from_user.id, target.from_user.username, target.from_user.first_name
        )
        user_id = user.id
        if not brand:  # подтягиваем последнее авто из профиля
            car = await get_last_car(user.id)
            if car is not None:
                brand, regimen = car.brand, car.regimen

    await state.set_data({"brand": brand, "regimen": regimen, "user_id": user_id})
    await state.set_state(BookingStates.date)
    await render(target, DATE_PROMPT, dates_kb())


@router.callback_query(menu_is("booking"))
async def open_booking(callback: CallbackQuery, state: FSMContext) -> None:
    await start_booking(callback, state)


# ---------------------------------------------------------------------------
# Шаг 1 — дата
# ---------------------------------------------------------------------------
@router.callback_query(date_is(), StateFilter(BookingStates.date))
async def choose_time(callback: CallbackQuery, state: FSMContext) -> None:
    iso = payload_value(callback.data)
    date_label, date_iso = parse_iso_date(iso)

    await state.update_data(date_label=date_label, date_iso=date_iso)
    await state.set_state(BookingStates.time)
    await render(callback, _time_prompt(date_label), time_kb())


@router.callback_query(date_is(), StateFilter("*"))
async def choose_time_out_of_context(callback: CallbackQuery, state: FSMContext) -> None:
    await start_booking(callback, state)


# ---------------------------------------------------------------------------
# Шаг 2 — время
# ---------------------------------------------------------------------------
@router.callback_query(time_is(), StateFilter(BookingStates.time))
async def show_confirmation(callback: CallbackQuery, state: FSMContext) -> None:
    time_value = payload_value(callback.data)
    data = await state.get_data()

    date_label = data.get("date_label")
    if not date_label:
        await state.set_state(BookingStates.date)
        await render(callback, DATE_PROMPT, dates_kb())
        return

    await state.update_data(time=time_value)
    await state.set_state(BookingStates.confirm)
    await render(
        callback,
        _confirm_text(data.get("brand"), data.get("regimen"), date_label, time_value),
        confirm_kb(),
    )


@router.callback_query(confirm_is("date"), StateFilter("*"))
async def back_to_dates(callback: CallbackQuery, state: FSMContext) -> None:
    """Вернуться к выбору даты, сохранив марку и регламент."""
    data = await state.get_data()
    await state.set_data(data)
    await state.set_state(BookingStates.date)
    await render(callback, DATE_PROMPT, dates_kb())


# ---------------------------------------------------------------------------
# Шаг 3 — подтверждение
# ---------------------------------------------------------------------------
@router.callback_query(confirm_is("ok"), StateFilter(BookingStates.confirm))
async def confirm_booking(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
) -> None:
    data = await state.get_data()
    date_label = data.get("date_label")
    date_iso = data.get("date_iso")
    time = data.get("time") or BOOKING_TIME

    if not date_label or not date_iso:
        await state.set_state(BookingStates.date)
        await render(callback, DATE_PROMPT, dates_kb())
        return

    # Защита от двойной отправки одной и той же заявки
    if await is_slot_taken(callback.from_user.id, date_iso, time):
        await state.clear()
        await render(
            callback,
            f"⚠️ У вас уже есть заявка на <b>{esc(date_label)}</b> в {esc(time)}.\n\n"
            "Нужно перенести — напишите об этом в чат или позвоните нам.",
            home_kb(),
        )
        return

    appointment = await create_appointment(
        user_id=data.get("user_id"),
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        brand=data.get("brand"),
        regimen=data.get("regimen"),
        date_label=date_label,
        date_iso=date_iso,
        time=time,
    )

    await state.clear()

    result_text = (
        "🎉 <b>Запись принята!</b>\n\n"
        f"📅 <b>{esc(date_label)}</b>, приём в <b>{esc(time)}</b>\n"
        f"⏰ Приезжайте к <b>{ARRIVAL_TIME}</b>.\n"
        f"🧾 Номер заявки: <code>#{appointment.id}</code>\n\n"
        "Мастер-приёмщик свяжется с вами, чтобы подтвердить визит. "
        "Если планы изменятся — просто напишите в чат.\n\n"
        f"📍 Ждём вас по адресу: {esc(ADDRESS)}"
    )
    await render(callback, result_text, done_kb())

    # Уведомления: Telegram администраторам + письмо через EmailJS
    await notify_admins(
        bot=bot,
        subject=f"Новая запись #{appointment.id}: {date_label} {time}",
        telegram_text=(
            "🔔 <b>Новая заявка на диагностику</b>\n\n"
            f"Заявка: <code>#{appointment.id}</code>\n"
            f"Дата: <b>{esc(date_label)}</b> ({esc(date_iso)})\n"
            f"Время: <b>{esc(time)}</b> (прибытие {ARRIVAL_TIME})\n"
            f"Авто: <b>{esc(data.get('brand') or '—')}</b>\n"
            f"Цель: <b>{esc(data.get('regimen') or 'диагностика')}</b>\n\n"
            f"Telegram: @{esc(callback.from_user.username or '—')}\n"
            f"ID: <code>{callback.from_user.id}</code>\n"
            f"Имя: {esc(callback.from_user.first_name or '—')}"
        ),
        email_lines=[
            f"Заявка #{appointment.id}",
            f"Дата: {date_label} ({date_iso})",
            f"Время приёма: {time}, прибытие: {ARRIVAL_TIME}",
            f"Автомобиль: {data.get('brand') or '—'}",
            f"Цель визита: {data.get('regimen') or 'диагностика'}",
            "",
            f"Telegram: @{callback.from_user.username or '—'}",
            f"Telegram ID: {callback.from_user.id}",
            f"Имя: {callback.from_user.first_name or '—'}",
        ],
    )


@router.callback_query(confirm_is("ok"), StateFilter("*"))
async def confirm_out_of_context(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(callback, MENU_TEXT, home_kb())


# ---------------------------------------------------------------------------
# Выход из сценария словами
# ---------------------------------------------------------------------------
@router.message(
    StateFilter(BookingStates.date, BookingStates.time, BookingStates.confirm),
    F.text,
)
async def booking_text_cancel(message: Message, state: FSMContext) -> None:
    """На шагах выбора даты/времени ждём нажатия кнопок; текстом можно выйти."""
    if is_cancel(message.text):
        await state.clear()
        return await render(message, MENU_TEXT, home_kb())

    await render(
        message,
        "👆 Дату и время выберите кнопками — так заявка не потеряется.",
        dates_kb(),
    )
    await state.set_state(BookingStates.date)
