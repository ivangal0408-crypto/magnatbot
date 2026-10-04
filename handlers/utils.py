"""
Вспомогательные функции хендлеров.

Главная идея — «чистый чат»: ответы на callback-кнопки редактируют то же
сообщение (edit_message_text), а ответы на текстовые сообщения по умолчанию
удаляют сообщение пользователя и выводят новый экран. Если нужно сохранить
сообщение пользователя (например, в ИИ-ассистенте) — передайте
delete_user_message=False.
"""

from __future__ import annotations

import logging
from html import escape as html_escape
from typing import Union

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

logger = logging.getLogger(__name__)

Markup = Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, None]


async def render(
    target: Union[Message, CallbackQuery],
    text: str,
    markup: Markup = None,
    *,
    delete_user_message: bool = True,
) -> None:
    """
    Показать экран:
    * callback — редактируем сообщение бота (без спама);
    * message — по умолчанию удаляем сообщение юзера и шлём новое.
      Если delete_user_message=False — сообщение юзера остаётся в чате.
    """
    if isinstance(target, CallbackQuery):
        message = target.message
        if message is None:
            await target.answer()
            return
        try:
            try:
                await message.edit_text(text, reply_markup=markup)
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    pass  # пользователь вернулся на тот же экран
                else:
                    # старое сообщение или устаревшая разметка — шлём новое
                    await message.answer(text, reply_markup=markup)
        except TelegramAPIError:
            logger.exception("Не удалось показать экран пользователю")
        await target.answer()
        return

    if delete_user_message:
        try:
            await target.delete()
        except TelegramAPIError:
            # удалить сообщение пользователя нельзя (не приватный чат) — не страшно
            pass

    await target.answer(text, reply_markup=markup)


def display_name(event: Union[Message, CallbackQuery]) -> str:
    """Имя пользователя для приветствия."""
    from_user = event.from_user
    if from_user is None:
        return "друг"
    return html_escape(from_user.first_name or from_user.username or "друг")


def esc(value: object) -> str:
    """Экранирование пользовательских данных для HTML-разметки."""
    return html_escape(str(value)) if value is not None else ""