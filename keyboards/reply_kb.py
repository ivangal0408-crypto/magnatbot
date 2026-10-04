"""
Reply-клавиатуры (обычные кнопки под полем ввода).

Основная навигация сделана на inline-кнопках (чтобы чат оставался чистым —
сообщения редактируются, а не дублируются), а reply-клавиатура — это быстрое
меню, которое всегда под рукой после /start. Выйти из пошагового сценария
можно любой кнопкой меню или словом «отмена».
"""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from keyboards.inline_kb import (
    BTN_AI,
    BTN_BOOKING,
    BTN_CALC,
    BTN_CONTACTS,
    BTN_PROFILE,
    BTN_RULES,
)

BTN_CANCEL = "⬅️ Отменить"

# Выйти из пошагового сценария можно кнопкой или словами
CANCEL_WORDS = frozenset(
    {
        "отмена",
        "отменить",
        "cancel",
        "стоп",
        "stop",
        BTN_CANCEL.lower(),
        "⬅️ главное меню",
    }
)


def is_cancel(text: str | None) -> bool:
    """Проверка «отмены» шага: кнопка или слово (без учёта регистра)."""
    if not text:
        return False
    return text.strip().lower() in CANCEL_WORDS


# Быстрое меню: то же, что и в inline, но всегда видно под полем ввода
_MENU_ROWS = (
    (BTN_RULES, BTN_AI),
    (BTN_CALC, BTN_BOOKING),
    (BTN_PROFILE, BTN_CONTACTS),
)


def main_reply_kb() -> ReplyKeyboardMarkup:
    """Постоянное быстрое меню (показывается на /start)."""
    builder = ReplyKeyboardBuilder()
    for row in _MENU_ROWS:
        builder.row(*row)
    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите раздел…",
    )
