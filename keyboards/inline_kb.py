"""
Inline-клавиатуры и callback-данные бота «Магнат Сервис».

Здесь же — генерация динамических дат для записи на диагностику.
"""

from __future__ import annotations

from datetime import date, timedelta

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    ADDRESS,
    ARRIVAL_TIME,
    BOOKING_DAYS_AHEAD,
    BOOKING_TIME,
    MAPS_URL,
    PHONE_DISPLAY,
    PHONE_TEL,
)

try:
    from aiogram.types import CopyText
except ImportError:
    CopyText = None  # type: ignore[assignment]

_WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


# ---------------------------------------------------------------------------
# Callback-данные
# ---------------------------------------------------------------------------
PREFIX_MENU = "menu"
PREFIX_NAV = "nav"          # nav:back, nav:home
PREFIX_CALC_REG = "calcreg"
PREFIX_CALC_ACT = "calcact"
PREFIX_DATE = "bkdate"
PREFIX_TIME = "bktime"
PREFIX_CONFIRM = "bkconf"


def payload_value(data: str | None) -> str:
    return (data or "").partition(":")[2]


def menu_cb(action: str) -> str:
    return f"{PREFIX_MENU}:{action}"


def menu_is(action: str):
    return F.data == menu_cb(action)


def nav_cb(action: str) -> str:
    return f"{PREFIX_NAV}:{action}"


def nav_is(action: str):
    return F.data == nav_cb(action)


def regimen_cb(code: str) -> str:
    return f"{PREFIX_CALC_REG}:{code}"


def regimen_is():
    return F.data.startswith(f"{PREFIX_CALC_REG}:")


def calc_action_cb(action: str) -> str:
    return f"{PREFIX_CALC_ACT}:{action}"


def calc_action_is(action: str):
    return F.data == calc_action_cb(action)


def date_cb(iso: str) -> str:
    return f"{PREFIX_DATE}:{iso}"


def date_is():
    return F.data.startswith(f"{PREFIX_DATE}:")


def time_cb(value: str) -> str:
    return f"{PREFIX_TIME}:{value}"


def time_is():
    return F.data.startswith(f"{PREFIX_TIME}:")


def confirm_cb(action: str) -> str:
    return f"{PREFIX_CONFIRM}:{action}"


def confirm_is(action: str):
    return F.data == confirm_cb(action)


# ---------------------------------------------------------------------------
# Тексты кнопок
# ---------------------------------------------------------------------------
BTN_RULES = "📋 Правила сервиса"
BTN_AI = "🤖 ИИ-ассистент"
BTN_CALC = "🧮 Калькулятор ТО"
BTN_BOOKING = "📅 Записаться"
BTN_CARS = "🚗 Автомобили"
BTN_PROFILE = "👤 Мой профиль"
BTN_CONTACTS = "ℹ️ О нас / Контакты"
BTN_BACK = "⬅️ Назад"
BTN_HOME = "🏠 Главное меню"
BTN_MY_BOOKINGS = "📅 Мои записи"

# Старое имя оставим как алиас, чтобы не сломать существующие импорты
BTN_MAIN_MENU_OLD = "⬅️ Главное меню"


def _nav_row() -> list[InlineKeyboardButton]:
    """Универсальный ряд: «Назад» + «Главное меню»."""
    return [
        InlineKeyboardButton(text=BTN_BACK, callback_data=nav_cb("back")),
        InlineKeyboardButton(text=BTN_HOME, callback_data=nav_cb("home")),
    ]


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------
def home_kb() -> InlineKeyboardMarkup:
    """Главное меню: 2 колонки."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_RULES, callback_data=menu_cb("rules"))
    builder.button(text=BTN_PROFILE, callback_data=menu_cb("profile"))
    builder.button(text=BTN_CARS, callback_data=menu_cb("cars"))
    builder.button(text=BTN_AI, callback_data=menu_cb("ai"))
    builder.button(text=BTN_CALC, callback_data=menu_cb("calc"))
    builder.button(text=BTN_BOOKING, callback_data=menu_cb("booking"))
    builder.button(text=BTN_MY_BOOKINGS, callback_data=menu_cb("my_bookings"))
    builder.button(text=BTN_CONTACTS, callback_data=menu_cb("contacts"))
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


def back_kb(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    """Любой экран: сверху contextual-кнопки, снизу «Назад» + «Главное меню»."""
    builder = InlineKeyboardBuilder()
    for row in extra_rows or []:
        builder.row(*row)
    builder.row(*_nav_row())
    return builder.as_markup()


def rules_kb() -> InlineKeyboardMarkup:
    """Экран правил: профиль / калькулятор / запись + навигация."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_PROFILE, callback_data=menu_cb("profile")),
        InlineKeyboardButton(text=BTN_CALC, callback_data=menu_cb("calc")),
    )
    builder.row(InlineKeyboardButton(text="📅 Записаться", callback_data=menu_cb("booking")))
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def contacts_kb() -> InlineKeyboardMarkup:
    """Контакты: карта, скопировать адрес + навигация."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📍 Открыть на карте", url=MAPS_URL)
    if CopyText is not None:
        builder.button(
            text="📋 Скопировать адрес",
            copy_text=CopyText(text=ADDRESS, label="Адрес скопирован"),
        )
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    """Профиль: быстрый переход к расчёту и записи + навигация."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=BTN_CALC, callback_data=menu_cb("calc")),
        InlineKeyboardButton(text=BTN_BOOKING, callback_data=menu_cb("booking")),
    )
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def ai_answer_kb() -> InlineKeyboardMarkup:
    """После ответа ассистента: записаться + навигация."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=BTN_BOOKING, callback_data=menu_cb("booking")))
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def calc_regimen_kb() -> InlineKeyboardMarkup:
    """Выбор регламента ТО."""
    builder = InlineKeyboardBuilder()
    for code, caption in (
        ("ТО-1", "ТО-1 · малое"),
        ("ТО-2", "ТО-2 · среднее"),
        ("ТО-3", "ТО-3 · большое"),
    ):
        builder.button(text=caption, callback_data=regimen_cb(code))
    builder.row(*_nav_row())
    builder.adjust(3, 1)
    return builder.as_markup()


def calc_result_kb() -> InlineKeyboardMarkup:
    """Итог расчёта: записаться / пересчитать + навигация."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Записаться", callback_data=calc_action_cb("booking")),
        InlineKeyboardButton(text="🔄 Пересчитать", callback_data=calc_action_cb("again")),
    )
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def dates_kb(days: tuple[int, ...] = BOOKING_DAYS_AHEAD) -> InlineKeyboardMarkup:
    """Динамические даты: 3, 4, 5, 6 дней от текущей — «27.08 (чт)»."""
    builder = InlineKeyboardBuilder()
    for offset in days:
        day = date.today() + timedelta(days=offset)
        builder.button(text=format_date_label(day), callback_data=date_cb(day.isoformat()))
    builder.row(*_nav_row())
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def time_kb() -> InlineKeyboardMarkup:
    """Время приёма строго 08:00, прибытие в 07:00."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🕗 {BOOKING_TIME} (прибытие в {ARRIVAL_TIME})",
        callback_data=time_cb(BOOKING_TIME),
    )
    builder.button(text="📅 Другая дата", callback_data=confirm_cb("date"))
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    """Подтверждение записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data=confirm_cb("ok"))
    builder.button(text="📅 Выбрать другую дату", callback_data=confirm_cb("date"))
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def done_kb() -> InlineKeyboardMarkup:
    """После успешной записи."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=BTN_CONTACTS, callback_data=menu_cb("contacts")))
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()

def user_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    """Список активных записей: под каждой — своя кнопка «Отменить»."""
    builder = InlineKeyboardBuilder()
    for b in bookings:
        builder.button(
            text=f"❌ Отменить #{b.id} · {b.date_label} {b.time}",
            callback_data=f"bk_cancel:{b.id}",
        )
    builder.row(*_nav_row())
    builder.adjust(1)
    return builder.as_markup()


def booking_cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    """Подтверждение отмены: да/нет."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отменить", callback_data=f"bk_cancel_ok:{booking_id}")
    builder.button(text="↩️ Нет, оставить", callback_data=menu_cb("my_bookings"))
    builder.adjust(1)
    return builder.as_markup()

# ---------------------------------------------------------------------------
# Работа с датами
# ---------------------------------------------------------------------------
def format_date_label(day: date) -> str:
    """2026-10-07 -> «07.10 (вт)»."""
    return f"{day.strftime('%d.%m')} ({_WEEKDAYS_RU[day.weekday()]})"


def parse_iso_date(iso: str) -> tuple[str, str]:
    """ISO-дата -> (метка «07.10 (вт)», ISO)."""
    day = date.fromisoformat(iso)
    return format_date_label(day), day.isoformat()