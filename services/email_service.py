"""
Уведомления о новых записях: Telegram администраторам + письмо через EmailJS.

EmailJS принимает обычные POST-запросы на https://api.emailjs.com/api/v1.0/email/send
с телом в формате:
{
  "service_id": "...",
  "template_id": "...",
  "user_id": "...",            (Public Key)
  "accessToken": "...",        (опционально, personal API key)
  "template_params": {"to_email": "...", "subject": "...", "message": "..."}
}
В шаблоне EmailJS используйте переменные {{subject}} и {{message}}.
"""

from __future__ import annotations

import logging

import aiohttp
from aiogram import Bot

from config import (
    ADMIN_IDS,
    EMAILJS_ACCESS_TOKEN,
    EMAILJS_API_URL,
    EMAILJS_SERVICE_ID,
    EMAILJS_TEMPLATE_ID,
    EMAILJS_USER_ID,
    NOTIFY_EMAIL,
)

logger = logging.getLogger(__name__)

EMAILJS_TIMEOUT = 20


def is_email_enabled() -> bool:
    """Хватает ли ключей EmailJS для отправки письма."""
    return bool(EMAILJS_SERVICE_ID and EMAILJS_TEMPLATE_ID and EMAILJS_USER_ID and NOTIFY_EMAIL)


async def send_email(subject: str, message: str) -> bool:
    """
    Отправка письма через EmailJS.
    Возвращает True, если EmailJS принял запрос.
    """
    if not is_email_enabled():
        logger.warning("EmailJS не настроен (EMAILJS_* / NOTIFY_EMAIL) — письмо пропущено")
        return False

    payload: dict[str, object] = {
        "service_id": EMAILJS_SERVICE_ID,
        "template_id": EMAILJS_TEMPLATE_ID,
        "user_id": EMAILJS_USER_ID,
        "template_params": {
            "to_email": NOTIFY_EMAIL,
            "to_name": "Магнат Сервис",
            "from_name": "Telegram-бот Магнат Сервис",
            "reply_to": NOTIFY_EMAIL,
            "subject": subject,
            "message": message,
        },
    }
    if EMAILJS_ACCESS_TOKEN:
        payload["accessToken"] = EMAILJS_ACCESS_TOKEN

    try:
        timeout = aiohttp.ClientTimeout(total=EMAILJS_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(EMAILJS_API_URL, json=payload) as response:
                body = await response.text()
                if response.status == 200:
                    logger.info("EmailJS: письмо «%s» отправлено", subject)
                    return True
                logger.error("EmailJS: HTTP %s — %s", response.status, body[:300])
                return False
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.error("EmailJS: ошибка отправки — %s", exc)
        return False


async def notify_telegram(bot: Bot, text: str) -> None:
    """Отправляет текст всем администраторам из ADMIN_IDS."""
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS пуст — уведомление в Telegram не отправлено")
        return

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as exc:  # noqa: BLE001 - логируем и идём дальше
            logger.error("Не удалось отправить уведомление админу %s: %s", admin_id, exc)


async def notify_admins(bot: Bot, subject: str, telegram_text: str, email_lines: list[str]) -> dict[str, bool]:
    """
    Комлексное уведомление о новой заявке.
    :param telegram_text: HTML-текст для Telegram
    :param email_lines: строки текстового письма
    """
    await notify_telegram(bot, telegram_text)

    email_ok = await send_email(subject=subject, message="\n".join(email_lines))
    if not email_ok:
        # Предупреждаем администраторов, что письмо не ушло, — чтобы не потеряли заявку
        await notify_telegram(
            bot,
            "⚠️ Письмо о новой заявке не отправлено (EmailJS). "
            "Заявка сохранена в базе — проверьте настройки EMAILJS_* в .env.",
        )

    return {"telegram": bool(ADMIN_IDS), "email": email_ok}
