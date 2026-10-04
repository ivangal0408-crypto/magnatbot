"""
Конфигурация бота «Магнат Сервис».

Все секреты берутся из переменных окружения (файл .env рядом с bot.py).
В коде нет токенов — только безопасные значения по умолчанию.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PRICE_LIST_PATH = DATA_DIR / "price_list.csv"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.txt"

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int = 0) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_ids(name: str) -> list[int]:
    raw = _env(name).replace(";", ",")
    result: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return result


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
BOT_TOKEN: str = _env("BOT_TOKEN")
ADMIN_IDS: list[int] = _env_ids("ADMIN_IDS")

# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------
DB_FILENAME: str = _env("DB_FILENAME", "magnat_service.db")
DB_URL: str = _env("DATABASE_URL", f"sqlite+aiosqlite:///{(BASE_DIR / DB_FILENAME).as_posix()}")

# ---------------------------------------------------------------------------
# ИИ-ассистент (AIAI.BY / VedAI Console)
# ---------------------------------------------------------------------------
VEDAI_API_URL: str = _env("VEDAI_API_URL", "https://vedai.by/api/v1/chat/completions")
VEDAI_API_KEY: str = _env("VEDAI_API_KEY")
VEDAI_MODEL: str = _env("VEDAI_MODEL", "VedAI")
VEDAI_TIMEOUT: int = _env_int("VEDAI_TIMEOUT", 40)
VEDAI_MAX_TOKENS: int = _env_int("VEDAI_MAX_TOKENS", 700)
VEDAI_TEMPERATURE: float = float(_env("VEDAI_TEMPERATURE", "0.3") or 0.3)
RAG_TOP_K: int = _env_int("RAG_TOP_K", 3)

# ---------------------------------------------------------------------------
# Данные автосервиса
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Магнат Сервис"
ADDRESS: str = "г. Минск, ул. Меньковский тракт, 5"
PHONE_DISPLAY: str = "+375 29 888 4777"
PHONE_TEL: str = "+375298884777"
MAPS_URL: str = "https://yandex.by/maps/29630/minsk-district/house/Zk4YcgVnSUAAQFtpfXR0cHpnYA==/?ll=27.427057%2C53.851644&z=16.99"

BOOKING_TIME: str = "08:00"
ARRIVAL_TIME: str = "07:00"
BOOKING_DAYS_AHEAD: tuple[int, ...] = (3, 4, 5, 6)

MILEAGE_SURCHARGE: float = 0.10
MILEAGE_SURCHARGE_FROM: int = 200_000


def missing_settings() -> list[str]:
    problems: list[str] = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN не задан — бот не сможет запуститься")
    if not VEDAI_API_KEY:
        problems.append("VEDAI_API_KEY не задан — ИИ-ассистент будет отвечать по базе знаний")
    if not ADMIN_IDS:
        problems.append("ADMIN_IDS не заданы — уведомления администратору не приходят")
    return problems