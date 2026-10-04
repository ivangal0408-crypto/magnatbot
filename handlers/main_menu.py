"""
Главное меню, /start, правила сервиса и экран «Мой профиль».

Экраны открываются и из inline-меню (callback), и из reply-клавиатуры (текст кнопки).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADDRESS, BOOKING_TIME, COMPANY_NAME, ARRIVAL_TIME
from database.db import get_or_create_user, get_user_profile
from keyboards.inline_kb import (
    BTN_AI,
    BTN_BOOKING,
    BTN_CALC,
    BTN_CONTACTS,
    BTN_PROFILE,
    BTN_RULES,
    contacts_kb,
    home_kb,
    menu_is,
    profile_kb,
    rules_kb,
)
from keyboards.reply_kb import main_reply_kb
from handlers.utils import display_name, esc, render

router = Router(name="main_menu")

MENU_TEXT = (
    f"🔧 <b>{COMPANY_NAME}</b> — автосервис в Минске\n\n"
    f"📍 {ADDRESS}\n"
    f"🕗 Приём автомобилей — с {BOOKING_TIME} (приезжайте к {ARRIVAL_TIME}, "
    "если вы с эвакуатора или на прицепе)\n\n"
    "Что я умею:\n"
    "• подсказать вероятную причину неисправности по симптому (ИИ-ассистент);\n"
    "• посчитать стоимость регламентного ТО по марке и пробегу;\n"
    "• записать на диагностику на удобное окно;\n"
    "• показать ваш профиль и историю заявок.\n\n"
    "Выберите раздел 👇"
)

RULES_TEXT = (
    "📋 <b>Правила сервиса</b>\n\n"
    "<b>1. Запись</b>\n"
    "• Диагностика и ТО — по предварительной записи, приём в 08:00.\n"
    f"• Приезжайте за 1 час до времени приёма (к {ARRIVAL_TIME}), чтобы мы успели "
    "принять авто и оформить наряд.\n"
    "• Перенести запись можно не позднее чем за 3 часа — просто напишите в чат.\n\n"
    "<b>2. Диагностика</b>\n"
    "• Сначала диагностика, потом работы. Итог — письменное заключение: причина, "
    "список работ, стоимость, сроки.\n"
    "• Без вашего согласия ничего не разбираем и не ремонтируем.\n\n"
    "<b>3. Оплата и запчасти</b>\n"
    "• Оплата по факту работ, чек/наряд выдаём обязательно.\n"
    "• Запчасти — ваши или наши (по согласованию, с чеком поставщика).\n"
    "• Работы, не вошедшие в регламент ТО, согласовываются отдельно.\n\n"
    "<b>4. Гарантия</b>\n"
    "• 6 месяцев или 10 000 км на выполненные работы (что наступит раньше).\n"
    "• Гарантия сохраняется при прохождении ТО по регламенту.\n\n"
    "<b>5. Честно</b>\n"
    "• Мы не ставим «точный диагноз» по переписке: ИИ-ассистент в этом боте "
    "показывает лишь <i>вероятные</i> причины, чтобы вы приехали подготовленным.\n"
    "• Всё, что требует разборки и замеров, проверяем только на подъёмнике."
)


# ---------------------------------------------------------------------------
# /start и главное меню
# ---------------------------------------------------------------------------
@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Регистрируем пользователя и показываем главное меню."""
    await state.clear()
    await get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    await message.answer(
        f"👋 <b>{display_name(message)}</b>, добро пожаловать!\n\n" + MENU_TEXT,
        reply_markup=main_reply_kb(),
    )


@router.message(Command("help"), StateFilter("*"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """/help — правила сервиса."""
    await state.clear()
    await render(message, RULES_TEXT, rules_kb())


@router.callback_query(menu_is("home"))
async def show_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «⬅️ Главное меню» — есть на каждом экране."""
    await state.clear()
    await render(callback, MENU_TEXT, home_kb())


# ---------------------------------------------------------------------------
# Быстрое меню (reply-клавиатура).
# Все текстовые кнопки обрабатываются здесь, в первом роутере, чтобы нажатие
# пункта меню всегда работало — в том числе посередине сценария FSM.
# ---------------------------------------------------------------------------
@router.message(F.text == BTN_RULES, StateFilter("*"))
async def menu_rules(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render(message, RULES_TEXT, rules_kb())


@router.message(F.text == BTN_PROFILE, StateFilter("*"))
async def menu_profile(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render(message, await build_profile_text(message), profile_kb())


@router.message(F.text == BTN_CONTACTS, StateFilter("*"))
async def menu_contacts(message: Message, state: FSMContext) -> None:
    from handlers.contacts import CONTACTS_TEXT

    await state.clear()
    await render(message, CONTACTS_TEXT, contacts_kb())


@router.message(F.text == BTN_AI, StateFilter("*"))
async def menu_ai(message: Message, state: FSMContext) -> None:
    from handlers.ai_assistant import start_assistant

    await start_assistant(message, state)


@router.message(F.text == BTN_CALC, StateFilter("*"))
async def menu_calc(message: Message, state: FSMContext) -> None:
    from handlers.calculator import start_calculator

    await start_calculator(message, state)


@router.message(F.text == BTN_BOOKING, StateFilter("*"))
async def menu_booking(message: Message, state: FSMContext) -> None:
    from handlers.booking import start_booking

    await start_booking(message, state)


# Пункты меню из inline-клавиатуры (callback)
@router.callback_query(menu_is("rules"))
async def show_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(callback, RULES_TEXT, rules_kb())


# ---------------------------------------------------------------------------
# Профиль
# ---------------------------------------------------------------------------
@router.callback_query(menu_is("profile"))
async def show_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render(callback, await build_profile_text(callback), profile_kb())


async def build_profile_text(event: Message | CallbackQuery) -> str:
    """Собираем текст экрана «Мой профиль» из БД."""
    from_user = event.from_user
    if from_user is None:
        return "Не удалось определить ваш аккаунт. Нажмите ⬅️ Главное меню."

    profile = await get_user_profile(from_user.id)
    if not profile.get("exists"):
        await get_or_create_user(from_user.id, from_user.username, from_user.first_name)
        profile = await get_user_profile(from_user.id)

    user = profile["user"]
    lines = [
        "👤 <b>Мой профиль</b>",
        "",
        f"Имя: <b>{esc(user.first_name)}</b>",
        f"Username: <b>{esc('@' + user.username) if user.username else '—'}</b>",
        f"Telegram ID: <code>{user.tg_id}</code>",
        f"В базе с: <b>{user.created_at.strftime('%d.%m.%Y')}</b>",
        "",
    ]

    cars = profile["cars"]
    if cars:
        lines.append("🚗 <b>Мои автомобили</b>")
        for car in cars[:5]:
            price = f", работа ≈ <b>{car.work_price:.0f} BYN</b>" if car.work_price else ""
            regimen = f", {esc(car.regimen)}" if car.regimen else ""
            lines.append(
                f"• <b>{esc(car.brand)}</b> — {car.mileage:,} км".replace(",", " ")
                + f"{regimen}{price}"
            )
    else:
        lines.append("🚗 Автомобилей пока нет — рассчитайте ТО в калькуляторе.")

    lines.append("")
    active = profile["active_bookings"]
    if active:
        lines.append("📅 <b>Активные записи</b>")
        for booking in active[:5]:
            status = "ожидает подтверждения" if booking.status == "new" else "подтверждена"
            lines.append(f"• <b>{esc(booking.date_label)}</b> в {esc(booking.time)} — {status}")
    else:
        lines.append("📅 Активных записей нет.")

    total = len(profile["bookings"])
    lines.append("")
    lines.append(f"Всего заявок за всё время: <b>{total}</b>")
    lines.append("")
    lines.append("Расчёт ТО ориентировочный: точная стоимость — после диагностики.")
    return "\n".join(lines)
