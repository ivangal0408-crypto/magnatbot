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

# Загружаем .env, если он лежит в корне проекта
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    """Безопасное чтение переменной окружения."""
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int = 0) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_ids(name: str) -> list[int]:
    """Список ID администраторов: '123,456' или '123;456'."""
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

# Кто получает уведомления о новых записях (через запятую)
ADMIN_IDS: list[int] = _env_ids("ADMIN_IDS")

# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------
DB_FILENAME: str = _env("DB_FILENAME", "magnat_service.db")
# as_posix() — чтобы путь корректно работал и на Windows (прямые слэши в URL)
DB_URL: str = _env("DATABASE_URL", f"sqlite+aiosqlite:///{(BASE_DIR / DB_FILENAME).as_posix()}")

# ---------------------------------------------------------------------------
# ИИ-ассистент (AIAI.BY / VedAI Console), формат OpenAI
# ---------------------------------------------------------------------------
VEDAI_API_URL: str = _env("VEDAI_API_URL", "https://vedai.by/api/v1/chat/completions")
VEDAI_API_KEY: str = _env("VEDAI_API_KEY")
VEDAI_MODEL: str = _env("VEDAI_MODEL", "VedAI")
VEDAI_TIMEOUT: int = _env_int("VEDAI_TIMEOUT", 40)
VEDAI_MAX_TOKENS: int = _env_int("VEDAI_MAX_TOKENS", 700)
VEDAI_TEMPERATURE: float = float(_env("VEDAI_TEMPERATURE", "0.3") or 0.3)

# Сколько фрагментов базы знаний подмешивать в контекст (RAG)
RAG_TOP_K: int = _env_int("RAG_TOP_K", 3)

# ---------------------------------------------------------------------------
# EmailJS (уведомления на почту)
# ---------------------------------------------------------------------------
EMAILJS_API_URL: str = _env("EMAILJS_API_URL", "https://api.emailjs.com/api/v1.0/email/send")
EMAILJS_SERVICE_ID: str = _env("EMAILJS_SERVICE_ID")
EMAILJS_TEMPLATE_ID: str = _env("EMAILJS_TEMPLATE_ID")
EMAILJS_USER_ID: str = _env("EMAILJS_USER_ID")
EMAILJS_ACCESS_TOKEN: str = _env("EMAILJS_ACCESS_TOKEN")
# Куда слать письмо с заявкой
NOTIFY_EMAIL: str = _env("NOTIFY_EMAIL")

# ---------------------------------------------------------------------------
# Данные автосервиса
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Магнат Сервис"
ADDRESS: str = "г. Минск, ул. Меньковский тракт, 5"
PHONE_DISPLAY: str = "+375 29 888 4777"
PHONE_TEL: str = "+375298884777"  # для ссылки tel:
MAPS_URL: str = "https://maps.google.com/?q=53.869944,27.620013"

# Запись на диагностику: приём строго в 08:00, приезжать нужно в 07:00
BOOKING_TIME: str = "08:00"
ARRIVAL_TIME: str = "07:00"

# На сколько дней вперёд показывать даты (3, 4, 5, 6 дней от текущей даты)
BOOKING_DAYS_AHEAD: tuple[int, ...] = (3, 4, 5, 6)

# Надбавка за большой пробег (> 200 000 км), доля от стоимости работ
MILEAGE_SURCHARGE: float = 0.10
MILEAGE_SURCHARGE_FROM: int = 200_000


def missing_settings() -> list[str]:
    """Что не настроено — бот запустится, но часть функций будет деградировать."""
    problems: list[str] = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN не задан — бот не сможет запуститься")
    if not VEDAI_API_KEY:
        problems.append("VEDAI_API_KEY не задан — ИИ-ассистент будет отвечать по базе знаний без нейросети")
    if not (EMAILJS_SERVICE_ID and EMAILJS_TEMPLATE_ID and EMAILJS_USER_ID):
        problems.append("Ключи EmailJS не заданы — письма на почту отправляться не будут")
    if not ADMIN_IDS:
        problems.append("ADMIN_IDS не заданы — уведомления администратору в Telegram не приходят")
    return problems
