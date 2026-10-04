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

# CopyText появился в aiogram 3.15 (Bot API 7.8). Если версия старше — кнопка
# «Скопировать адрес» просто не будет добавлена.
try:  # pragma: no cover - зависит от версии aiogram
    from aiogram.types import CopyText
except ImportError:  # pragma: no cover
    CopyText = None  # type: ignore[assignment]

# Краткие названия дней недели для формата «27.08 (чт)»
_WEEKDAYS_RU = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")


# ---------------------------------------------------------------------------
# Callback-данные
#
# Payload кнопок формируем строкой вида «префикс:значение», а фильтрацию
# в хендлерах делаем через F.data — такой способ одинаково работает во всех
# версиях aiogram 3.x и не зависит от внутренних хелперов фреймворка.
# ---------------------------------------------------------------------------
PREFIX_MENU = "menu"  # menu:home, menu:rules, menu:ai, menu:calc, ...
PREFIX_CALC_REG = "calcreg"  # calcreg:ТО-1
PREFIX_CALC_ACT = "calcact"  # calcact:again, calcact:booking
PREFIX_DATE = "bkdate"  # bkdate:2026-10-07
PREFIX_TIME = "bktime"  # bktime:08:00
PREFIX_CONFIRM = "bkconf"  # bkconf:ok, bkconf:date


def payload_value(data: str | None) -> str:
    """Достаёт значение из payload вида «prefix:value» (значение с ':' внутри ок)."""
    return (data or "").partition(":")[2]


def menu_cb(action: str) -> str:
    return f"{PREFIX_MENU}:{action}"


def menu_is(action: str):
    """Фильтр: нажата кнопка меню с указанным действием."""
    return F.data == menu_cb(action)


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
# Тексты пунктов меню (используются и в inline, и в reply-клавиатуре)
# ---------------------------------------------------------------------------
BTN_RULES = "📋 Правила сервиса"
BTN_AI = "🤖 ИИ-ассистент"
BTN_CALC = "🧮 Калькулятор ТО"
BTN_BOOKING = "📅 Записаться на диагностику"
BTN_PROFILE = "👤 Мой профиль"
BTN_CONTACTS = "ℹ️ О нас / Контакты"
BTN_BACK = "⬅️ Главное меню"


# ---------------------------------------------------------------------------
# Клавиатуры
# ---------------------------------------------------------------------------
def home_kb() -> InlineKeyboardMarkup:
    """Главное меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_RULES, callback_data=menu_cb("rules"))
    builder.button(text=BTN_AI, callback_data=menu_cb("ai"))
    builder.button(text=BTN_CALC, callback_data=menu_cb("calc"))
    builder.button(text=BTN_BOOKING, callback_data=menu_cb("booking"))
    builder.button(text=BTN_PROFILE, callback_data=menu_cb("profile"))
    builder.button(text=BTN_CONTACTS, callback_data=menu_cb("contacts"))
    builder.adjust(1)
    return builder.as_markup()


def back_kb(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    """Любой экран: сверху contextual-кнопки, снизу «⬅️ Главное меню»."""
    builder = InlineKeyboardBuilder()
    for row in extra_rows or []:
        builder.row(*row)
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    return builder.as_markup()


def rules_kb() -> InlineKeyboardMarkup:
    """Экран правил: профиль / калькулятор / запись / главное меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text=BTN_PROFILE, callback_data=menu_cb("profile"))
    builder.button(text=BTN_CALC, callback_data=menu_cb("calc"))
    builder.row(InlineKeyboardButton(text="📅 Записаться", callback_data=menu_cb("booking")))
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(1)
    return builder.as_markup()


def contacts_kb() -> InlineKeyboardMarkup:
    """Контакты: позвонить, открыть карту, скопировать адрес."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📞 Позвонить {PHONE_DISPLAY}", url=f"tel:{PHONE_TEL}")
    builder.button(text="📍 Открыть на карте", url=MAPS_URL)
    if CopyText is not None:
        builder.button(
            text="📋 Скопировать адрес",
            copy_text=CopyText(text=ADDRESS, label="Адрес скопирован"),
        )
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(1)
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    """Профиль: быстрый переход к расчёту и записи."""
    return back_kb(
        [
            [
                InlineKeyboardButton(text=BTN_CALC, callback_data=menu_cb("calc")),
                InlineKeyboardButton(text=BTN_BOOKING, callback_data=menu_cb("booking")),
            ]
        ]
    )


def ai_answer_kb() -> InlineKeyboardMarkup:
    """После ответа ассистента: записаться или в меню."""
    return back_kb(
        [
            [
                InlineKeyboardButton(
                    text=BTN_BOOKING, callback_data=menu_cb("booking")
                )
            ]
        ]
    )


def calc_regimen_kb() -> InlineKeyboardMarkup:
    """Выбор регламента ТО."""
    builder = InlineKeyboardBuilder()
    for code, caption in (
        ("ТО-1", "ТО-1 · малое"),
        ("ТО-2", "ТО-2 · среднее"),
        ("ТО-3", "ТО-3 · большое"),
    ):
        builder.button(text=caption, callback_data=regimen_cb(code))
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(3, 1)
    return builder.as_markup()


def calc_result_kb() -> InlineKeyboardMarkup:
    """Итог расчёта: записаться / пересчитать / меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data=calc_action_cb("booking"))
    builder.button(text="🔄 Пересчитать", callback_data=calc_action_cb("again"))
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(2, 1)
    return builder.as_markup()


def dates_kb(days: tuple[int, ...] = BOOKING_DAYS_AHEAD) -> InlineKeyboardMarkup:
    """Динамические даты: 3, 4, 5, 6 дней от текущей — «27.08 (чт)»."""
    builder = InlineKeyboardBuilder()
    for offset in days:
        day = date.today() + timedelta(days=offset)
        builder.button(text=format_date_label(day), callback_data=date_cb(day.isoformat()))
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
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
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    """Подтверждение записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data=confirm_cb("ok"))
    builder.button(text="📅 Выбрать другую дату", callback_data=confirm_cb("date"))
    builder.button(text=BTN_BACK, callback_data=menu_cb("home"))
    builder.adjust(1)
    return builder.as_markup()


def done_kb() -> InlineKeyboardMarkup:
    """После успешной записи."""
    return back_kb(
        [[InlineKeyboardButton(text=BTN_CONTACTS, callback_data=menu_cb("contacts"))]]
    )


# ---------------------------------------------------------------------------
# Работа с датами
# ---------------------------------------------------------------------------
def format_date_label(day: date) -> str:
    """2026-10-07 -> «07.10 (вт)»."""
    return f"{day.strftime('%d.%m')} ({_WEEKDAYS_RU[day.weekday()]})"


def parse_iso_date(iso: str) -> tuple[str, str]:
    """ISO-дата -> (метка «07.10 (вт)», ISO). Нужна для подписи callback'а."""
    day = date.fromisoformat(iso)
    return format_date_label(day), day.isoformat()
