"""
ИИ-ассистент (RAG): пользователь описывает симптом своими словами,
бот подбирает блоки из data/knowledge_base.txt и спрашивает у VedAI
вероятную причину и рекомендацию. Ответ редактируется в одном сообщении.

Также здесь лежит «последний» обработчик текста: если update не подошёл
ни одному роутеру, подсказываем меню.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import COMPANY_NAME
from handlers.main_menu import MENU_TEXT
from handlers.utils import esc, render
from keyboards.inline_kb import ai_answer_kb, back_kb, home_kb, menu_is
from keyboards.reply_kb import is_cancel
from services.rag_service import answer_question

router = Router(name="ai_assistant")
logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 600
# Лимит текста сообщения в Telegram — 4096 символов, берём с запасом
MAX_MESSAGE_LENGTH = 3900

INTRO_TEXT = (
    "🤖 <b>ИИ-ассистент сервиса</b>\n\n"
    "Опишите, что происходит с автомобилем, своими словами — как рассказали бы "
    "знакомому механику. Например:\n"
    "• «пинается коробка при переключении с 1 на 2»;\n"
    "• «гремит на кочках на небольшой скорости»;\n"
    "• «жрёт бензин больше обычного, тяга пропала»;\n"
    "• «вибрирует руль на 90–110 км/ч».\n\n"
    "Что важно: ассистент говорит о <i>вероятных</i> причинах по базе типовых "
    "обращений сервиса. Это не диагноз — точную причину назовём после диагностики.\n\n"
    "Напишите симптомы 👇"
)

THINKING_TEXT = "⏳ Смотрю по базе типовых обращений сервиса…"


class AiStates(StatesGroup):
    question = State()


async def start_assistant(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Открывает экран ассистента."""
    await state.clear()
    await state.set_state(AiStates.question)
    await render(target, INTRO_TEXT, back_kb())


@router.callback_query(menu_is("ai"))
async def open_ai(callback: CallbackQuery, state: FSMContext) -> None:
    await start_assistant(callback, state)


@router.message(StateFilter(AiStates.question), F.text)
async def process_question(message: Message, state: FSMContext) -> None:
    """Получили описание симптома — уходим в RAG и редактируем сообщение с ответом."""
    if is_cancel(message.text):
        await state.clear()
        return await render(message, MENU_TEXT, home_kb())

    question = " ".join((message.text or "").split())
    if len(question) < 8:
        await message.answer(
            "Расскажите чуть подробнее: что происходит, когда и на какой скорости. "
            "Например: <i>«пинается автомат при трогании»</i>."
        )
        return

    question = question[:MAX_QUESTION_LENGTH]

    # «Читаем» ответ в том же сообщении, чтобы не спамить
    await state.clear()
    try:
        await message.delete()
    except TelegramAPIError:
        pass  # сообщение пользователя мог удалиться или чат не приватный
    thinking = await message.answer(THINKING_TEXT)

    answer, source, _titles = await answer_question(question)

    # Ответ нейросети — обычный текст: экранируем, чтобы HTML-разметка не сломала отправку.
    # Формированный нами ответ по базе знаний уже содержит теги — его не трогаем.
    if source == "vedai":
        text = esc(answer)
    else:
        text = answer + "\n\n<i>Ответ собран по базе типовых обращений сервиса.</i>"

    # Лимит сообщения Telegram — 4096 символов
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 20].rstrip() + "\n…(продолжение уточните у мастера)"

    try:
        await thinking.edit_text(text, reply_markup=ai_answer_kb())
    except TelegramAPIError:
        logger.exception("Не удалось отредактировать ответ ассистента, отправляем новый")
        await render(message, text, ai_answer_kb())


@router.message(StateFilter(AiStates.question), ~F.text)
async def process_not_text(message: Message, state: FSMContext) -> None:
    """Фото/голос/стикер вместо описания симптома."""
    await render(
        message,
        "📝 Опишите проблему текстом — так ассистент точнее подберёт похожие случаи.",
        back_kb(),
    )


# ---------------------------------------------------------------------------
# Финальный обработчик: текст, который не распознал ни один роутер
# (этот роутер подключён последним, поэтому не мешает FSM-сценариям)
# ---------------------------------------------------------------------------
@router.message(F.text, StateFilter(None))
async def unknown_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render(
        message,
        f"🤔 Не понял. Я бот сервиса <b>{COMPANY_NAME}</b> и умею считать ТО, "
        "консультировать по симптомам и записывать на диагностику.\n\n"
        "Выберите раздел 👇",
        home_kb(),
    )
