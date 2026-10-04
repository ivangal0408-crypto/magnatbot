"""
Калькулятор стоимости ТО.

Сценарий (FSM): марка → пробег → регламент (ТО-1/ТО-2/ТО-3) → расчёт по
data/price_list.csv → результат с кнопкой «Записаться».
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import MILEAGE_SURCHARGE, MILEAGE_SURCHARGE_FROM, PRICE_LIST_PATH
from database.db import get_or_create_user, save_car
from handlers.main_menu import MENU_TEXT
from handlers.utils import esc, render
from keyboards.inline_kb import (
    back_kb,
    calc_action_is,
    calc_regimen_kb,
    calc_result_kb,
    home_kb,
    menu_is,
    payload_value,
    regimen_is,
)
from keyboards.reply_kb import is_cancel

router = Router(name="calculator")

# Кэш прайс-листа: путь -> {(ключ_марки, регламент): цена}
_PRICE_CACHE: dict[str, dict[tuple[str, str], float]] = {}
# Отображаемые названия марок и их алиасы
_TITLE_CACHE: dict[str, str] = {}
_ALIAS_CACHE: dict[str, list[str]] = {}


class CalcStates(StatesGroup):
    brand = State()
    mileage = State()
    regimen = State()


# ---------------------------------------------------------------------------
# Прайс-лист
# ---------------------------------------------------------------------------
def _normalize(value: str) -> str:
    """Приводит строку к виду для сравнения: нижний регистр, без ё и мусора."""
    value = (value or "").lower().replace("ё", "е").strip()
    return re.sub(r"[^0-9a-zа-я]+", " ", value)


def load_price_list(path: Path = PRICE_LIST_PATH) -> dict[tuple[str, str], float]:
    """
    Читает CSV вида: brand_key,display,aliases,to_type,work_price
    Возвращает {(ключ_марки, регламент): цена_работ}.
    """
    key = str(path)
    if key in _PRICE_CACHE:
        return _PRICE_CACHE[key]

    prices: dict[tuple[str, str], float] = {}
    titles: dict[str, str] = {}

    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                brand_key = (row.get("brand_key") or "").strip().lower()
                regimen = (row.get("to_type") or "").strip().upper()
                raw_price = (row.get("work_price") or "").strip().replace(",", ".")
                if not brand_key or not regimen:
                    continue
                try:
                    price = float(raw_price)
                except ValueError:
                    continue
                prices[(brand_key, regimen)] = price
                titles[brand_key] = (row.get("display") or brand_key).strip()

                # Алиасы («ауди|ауди а6|ауди а4») читаем один раз
                raw_aliases = (row.get("aliases") or "").replace("|", ";")
                aliases = _ALIAS_CACHE.setdefault(brand_key, [])
                for item in raw_aliases.split(";"):
                    normalized = _normalize(item)
                    if normalized and normalized not in aliases:
                        aliases.append(normalized)

    _PRICE_CACHE[key] = prices
    _TITLE_CACHE.update(titles)
    return prices


def match_brand(user_input: str) -> str:
    """
    Определяет ключ марки по вводу пользователя.
    Сопоставляем по ключу, отображаемому имени и алиасам из CSV;
    если ничего не подошло — возвращаем '*'.
    """
    prices = load_price_list()
    text = _normalize(user_input)

    # Сначала более длинные названия, чтобы «land rover» не схлопнулся в «land»
    for brand_key in sorted({key[0] for key in prices}, key=len, reverse=True):
        if brand_key == "*":
            continue
        display = _normalize(_TITLE_CACHE.get(brand_key, brand_key))
        for candidate in (display, brand_key, *_ALIAS_CACHE.get(brand_key, [])):
            if candidate and candidate in text:
                return brand_key

    return "*"


def calc_work_price(brand_key: str, regimen: str, mileage: int) -> tuple[float, float, str]:
    """
    Считает стоимость работ.
    Возвращает (база, итого, пояснение про коэффициент).
    """
    prices = load_price_list()
    base = prices.get((brand_key, regimen))
    if base is None:
        base = prices.get(("*", regimen))
    if base is None:  # прайс пустой или регламент неизвестен — страховка
        base = {"ТО-1": 90.0, "ТО-2": 170.0, "ТО-3": 280.0}.get(regimen, 150.0)

    surcharge = 0.0
    note = ""
    if mileage >= MILEAGE_SURCHARGE_FROM:
        surcharge = round(base * MILEAGE_SURCHARGE, 2)
        note = (
            f"Пробег ≥ {MILEAGE_SURCHARGE_FROM:,} км — коэффициент "
            f"+{int(MILEAGE_SURCHARGE * 100)}% (увеличенный износ, "
            "дополнительный осмотр)".replace(",", " ")
        )

    return base, round(base + surcharge, 2), note


# ---------------------------------------------------------------------------
# Экраны
# ---------------------------------------------------------------------------
BRAND_PROMPT = (
    "🧮 <b>Калькулятор ТО — шаг 1 из 3</b>\n\n"
    "Напишите марку автомобиля, как видите её в СТС: "
    "<i>Audi A6, BMW X3, Kia Rio, Geely Coolray</i>.\n\n"
    "Если нужна отмена — напишите <code>отмена</code> или выберите другой раздел в меню."
)


def _mileage_prompt(brand: str) -> str:
    return (
        f"🚗 Марка: <b>{esc(brand)}</b>\n\n"
        "🧮 <b>Калькулятор ТО — шаг 2 из 3</b>\n\n"
        "Напишите текущий пробег в километрах, цифрами.\n"
        "Примеры: <code>87000</code>, <code>87 000</code>, <code>165000</code>"
    )


def _regimen_prompt(brand: str, mileage: int) -> str:
    return (
        f"🚗 <b>{esc(brand)}</b>, пробег <b>{mileage:,} км</b>\n\n".replace(",", " ")
        + "🧮 <b>Калькулятор ТО — шаг 3 из 3</b>\n\n"
        "Выберите регламент обслуживания:\n"
        "• <b>ТО-1</b> — малое: масло + фильтры, базовый осмотр (до ~60 000 км);\n"
        "• <b>ТО-2</b> — среднее: масло, фильтры, свечи/тормозная жидкость, диагностика;\n"
        "• <b>ТО-3</b> — большое: всё из ТО-2 + ремни/ролики, жидкость АКПП, осмотр ходовой.\n\n"
        "Если не знаете — напишите ИИ-ассистенту или выберите по пробегу."
    )


def _result_text(brand: str, mileage: int, regimen: str, base: float, total: float, note: str) -> str:
    lines = [
        "🧮 <b>Расчёт стоимости работ</b>",
        "",
        f"🚗 Марка: <b>{esc(brand)}</b>",
        f"📏 Пробег: <b>{mileage:,} км</b>".replace(",", " "),
        f"🔧 Регламент: <b>{regimen}</b>",
        "",
        f"Работы по регламенту: <b>{base:.0f} BYN</b>",
    ]
    if note:
        lines.append(f"Коэффициент: <i>{note}</i>")
    lines += [
        "",
        f"💰 <b>Итого стоимость работ: {total:.0f} BYN</b>",
        "",
        "Запчасти (масло, фильтры, расходники) считаются отдельно по прайсу "
        "и согласовываются до начала работ.",
        "Расчёт ориентировочный: точную сумму назовём после диагностики.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Валидация ввода
# ---------------------------------------------------------------------------
def _parse_mileage(raw: str) -> int | None:
    """Достаёт пробег из строки вида '165 000 км'."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    value = int(digits)
    if value > 1_500_000:  # явная опечатка
        return None
    return value


def _looks_like_brand(raw: str) -> bool:
    return bool(re.search(r"[A-Za-zА-Яа-яЁё]{2,}", raw or "")) and len(raw.strip()) <= 40


# ---------------------------------------------------------------------------
# Хендлеры
# ---------------------------------------------------------------------------
async def start_calculator(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Запуск калькулятора из любого меню."""
    await state.clear()
    await state.set_state(CalcStates.brand)
    await render(target, BRAND_PROMPT, back_kb())


async def cancel_calculator(message: Message, state: FSMContext) -> None:
    """Выход из сценария по слову «отмена»."""
    await state.clear()
    await render(message, MENU_TEXT, home_kb())


@router.callback_query(menu_is("calc"))
async def open_calc(callback: CallbackQuery, state: FSMContext) -> None:
    await start_calculator(callback, state)


@router.message(StateFilter(CalcStates.brand), F.text)
async def ask_mileage(message: Message, state: FSMContext) -> None:
    """Шаг 1 — марка."""
    if is_cancel(message.text):
        return await cancel_calculator(message, state)

    raw = (message.text or "").strip()
    if not _looks_like_brand(raw):
        await message.answer(
            "🤔 Похоже, это не марка. Напишите название, например <code>Audi</code> "
            "или <code>Kia Rio</code>.",
        )
        return

    brand = raw[:40]
    await state.update_data(brand=brand)
    await state.set_state(CalcStates.mileage)
    await render(message, _mileage_prompt(brand), back_kb())


@router.message(StateFilter(CalcStates.mileage), F.text)
async def ask_regimen(message: Message, state: FSMContext) -> None:
    """Шаг 2 — пробег."""
    if is_cancel(message.text):
        return await cancel_calculator(message, state)

    mileage = _parse_mileage(message.text or "")
    if mileage is None or mileage <= 0:
        await message.answer(
            "Пробег не понял. Напишите цифрами, например <code>127500</code>."
        )
        return

    data = await state.get_data()
    brand = data.get("brand", "автомобиль")
    await state.update_data(mileage=mileage)
    await state.set_state(CalcStates.regimen)
    await render(message, _regimen_prompt(brand, mileage), calc_regimen_kb())


@router.callback_query(regimen_is(), StateFilter(CalcStates.regimen))
async def show_result(callback: CallbackQuery, state: FSMContext) -> None:
    """Шаг 3 — регламент и расчёт."""
    data = await state.get_data()
    brand = data.get("brand")
    mileage = int(data.get("mileage") or 0)

    if not brand:  # состояние потеряно (например, бот перезапустился)
        await start_calculator(callback, state)
        return

    regimen = payload_value(callback.data).upper()
    brand_key = match_brand(brand)
    display_brand = _TITLE_CACHE.get(brand_key, brand) if brand_key != "*" else brand
    base, total, note = calc_work_price(brand_key, regimen, mileage)

    # Сохраняем авто и расчёт в БД — пригодится в профиле и при записи
    user = await get_or_create_user(
        callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )
    await save_car(user.id, display_brand, mileage, regimen, total)

    await state.update_data(regimen=regimen, total=total, brand_display=display_brand)
    await state.set_state(None)

    await render(
        callback,
        _result_text(display_brand, mileage, regimen, base, total, note),
        calc_result_kb(),
    )


@router.callback_query(regimen_is(), StateFilter("*"))
async def regimen_out_of_context(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка регламента нажатая после сброса состояния — начинаем заново."""
    await start_calculator(callback, state)


@router.callback_query(calc_action_is("again"))
async def calc_again(callback: CallbackQuery, state: FSMContext) -> None:
    await start_calculator(callback, state)


@router.callback_query(calc_action_is("booking"))
async def calc_to_booking(callback: CallbackQuery, state: FSMContext) -> None:
    """Из результата расчёта сразу в запись, с маркой и регламентом."""
    from handlers.booking import start_booking

    data = await state.get_data()
    await start_booking(
        callback,
        state,
        brand=data.get("brand_display") or data.get("brand"),
        regimen=data.get("regimen"),
    )
