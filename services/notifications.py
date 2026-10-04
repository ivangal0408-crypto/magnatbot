"""
Уведомления о новых заявках — только в Telegram администраторам.
"""

from __future__ import annotations

import logging

from aiogram import Bot

from config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, telegram_text: str) -> dict[str, bool]:
    """
    Отправляет уведомление о новой заявке всем администраторам.

    :param telegram_text: HTML-текст для Telegram
    """
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS пуст — уведомление не отправлено")
        return {"telegram": False}

    sent = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, telegram_text)
            sent = True
        except Exception as exc:  # noqa: BLE001
            logger.error("Не удалось отправить уведомление админу %s: %s", admin_id, exc)

    return {"telegram": sent}