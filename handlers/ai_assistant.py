"""
ИИ-ассистент (RAG): пользователь описывает симптом своими словами,
бот подбирает блоки из data/knowledge_base.txt и спрашивает у VedAI
вероятную причину и рекомендацию.
"""

from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import COMPANY_NAME
from handlers.main_menu import MENU_TEXT
from handlers.utils import render
from keyboards.inline_kb import ai_answer_kb, back_kb, home_kb, menu_is
from keyboards.reply_kb import is_cancel
from services.rag_service import answer_question

router = Router(name="ai_assistant")
logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 600
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

# Какие HTML-теги разрешены в ответе ИИ (Telegram поддерживает именно эти)
_ALLOWED_TAGS = re.compile(r"</?(b|strong|i|em|u|s|code|pre|a)(\s[^>]*)?>", re.IGNORECASE)


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

    # Показываем «печатаю…», не удаляя сообщение пользователя
    await state.clear()
    thinking = await message.answer(THINKING_TEXT)

    answer, source, _titles = await answer_question(question)

    # Заменяем «thinking» на нормальный ответ
    text = _clean_ai_answer(answer)

    if source == "knowledge_base":
        text += "\n\n<i>Ответ собран по базе типовых обращений сервиса.</i>"

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[: MAX_MESSAGE_LENGTH - 20].rstrip() + "\n…(продолжение уточните у мастера)"

    try:
        await thinking.edit_text(text, reply_markup=ai_answer_kb())
    except TelegramAPIError:
        logger.exception("Не удалось отредактировать ответ ассистента, отправляем новый")
        await message.answer(text, reply_markup=ai_answer_kb())


def _clean_ai_answer(text: str) -> str:
    """
    Убираем markdown-обёртки (**текст**, ## заголовки), которые модель иногда всё же
    добавляет, и оставляем только безопасные HTML-теги для Telegram.
    """
    # **жирный** → <b>жирный</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # *курсив* → <i>курсив</i>
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    # ## заголовки → жирная строка
    text = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # ```код``` → <code>код</code>
    text = re.sub(r"```(.+?)```", r"<code>\1</code>", text, flags=re.DOTALL)
    # `код` → <code>код</code>
    text = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", text)
    # Экранируем амперсанды/угловые скобки, которые не являются нашими тегами
    # (осторожный шаг — модель обычно их не использует, но подстрахуемся)
    text = _escape_unknown_tags(text)
    return text.strip()


def _escape_unknown_tags(text: str) -> str:
    """Оставляет только разрешённые HTML-теги, остальные <...> экранирует."""
    def _repl(match: re.Match) -> str:
        tag = match.group(0)
        if _ALLOWED_TAGS.match(tag):
            return tag
        # Экранируем только угловые скобки, не трогая содержимое
        return tag.replace("<", "&lt;").replace(">", "&gt;")

    return re.sub(r"<[^>]+>", _repl, text)


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