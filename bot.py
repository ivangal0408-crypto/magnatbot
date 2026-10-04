"""Точка входа: инициализация бота, реестр роутеров, запуск long polling."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, COMPANY_NAME, missing_settings
from database.db import init_db
from handlers import routers

logger = logging.getLogger("magnat")


async def on_startup(bot: Bot) -> None:
    """Создаём таблицы, подсказки команд и меню бота."""
    await init_db()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Правила сервиса"),
            BotCommand(command="contacts", description="Адрес и телефон"),
        ]
    )
    await bot.set_my_description(
        f"Бот автосервиса {COMPANY_NAME}: ИИ-помощник по симптомам, "
        "калькулятор ТО и запись на диагностику."
    )
    logger.info("Бот запущен. База данных готова.")


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен "
            "бота от @BotFather."
        )

    for problem in missing_settings():
        logger.warning("Настройка: %s", problem)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(*routers)
    dp.startup.register(on_startup)

    try:
        # Не обрабатываем старые сообщения, накопившиеся пока бот был выключен
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code:
            print(exc.code)  # noqa: T201 - осознанный вывод подсказки в консоль
        else:
            print("Бот остановлен.")  # noqa: T201
