"""
RAG-ассистент для подбора вероятной причины неисправности.

Как это работает:
1) читаем data/knowledge_base.txt и режем её на блоки по разделителям «###»;
2) по запросу пользователя выбираем top_k самых близких блоков (лемматизации нет,
   поэтому используем нормализацию, токены и подстроки — этого достаточно для
   «народных» формулировок вроде «пинается коробка»);
3) собираем промпт с контекстом и отправляем в VedAI Console (AIAI.BY) —
   формат OpenAI chat/completions;
4) если API недоступно, отвечаем по базе знаний напрямую (без нейросети),
   чтобы бот не молчал.

Ответ всегда подаётся как «вероятная причина + рекомендация записаться»,
без точного диагноза.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

import aiohttp

from config import (
    KNOWLEDGE_BASE_PATH,
    RAG_TOP_K,
    VEDAI_API_KEY,
    VEDAI_API_URL,
    VEDAI_MAX_TOKENS,
    VEDAI_MODEL,
    VEDAI_TEMPERATURE,
    VEDAI_TIMEOUT,
)

# Стоп-слова и «вода», которые не несут диагностической ценности
_STOP_WORDS = {
    "моя", "моей", "мою", "машин", "машина", "авто", "автомобил", "автомобиля",
    "машинк", "проблема", "сломал", "сломалось", "поломк", "что", "как", "почему",
    "почемуто", "может", "быть", "кажется", "какое", "какой", "какая", "это", "тут",
    "есть", "было", "быть", "очень", "сильно", "постоянно", "иногда", "когда",
    "на", "не", "но", "ну", "да", "нет", "у", "в", "во", "с", "со", "к", "по",
    "из", "для", "про", "при", "мне", "меня", "я", "ты", "он", "она", "оно", "они",
    "вчера", "сегодня", "завтра", "поехал", "поехала", "стоит", "стоитли",
}

# «Народные» формулировки -> технические термины из базы знаний
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "пина": ("акпп", "автомат", "толчок", "ричок", "пинок"),
    "пинается": ("акпп", "автомат", "толчок", "ричок"),
    "толкается": ("акпп", "автомат", "толчок", "гидротрансформатор"),
    "ричок": ("акпп", "толчок", "подушка", "опора"),
    "гремит": ("стук", "кочк", "подвеск", "стойк", "стабилизатор"),
    "стучит": ("стук", "подвеск", "рулев", "шрус"),
    "булька": ("жидкость", "помпа", "воздушная", "охлаждающ"),
    "жрет": ("расход", "бензин", "смесе", "лямбда", "катушк", "форсунк"),
    "жрёт": ("расход", "бензин", "смесе", "лямбда"),
    "расход": ("расход", "бензин", "смесе"),
    "не тянет": ("тяга", "турбин", "топливн", "катушк", "фильтр"),
    "троит": ("троен", "катушк", "свеч", "компресс", "форсунк"),
    "вибрир": ("вибрац", "балансировк", "шрус", "подушка", "диски"),
    "дрожит": ("вибрац", "тормозн", "диски", "балансировк"),
    "уводит": ("увод", "развал", "сход", "шин", "ступиц"),
    "ведет": ("увод", "развал", "сход", "тормозн"),
    "скрип": ("скрип", "тормозн", "колодк", "ремень", "натяжитель"),
    "свист": ("ремень", "натяжитель", "ролик", "турбин"),
    "гудит": ("гудет", "ступиц", "подшипник", "редуктор", "гидротрансформатор"),
    "горят": ("лампа", "check", "ошибк", "датчик"),
    "check": ("ошибк", "лямбда", "катушк", "датчик"),
    "дым": ("дым", "маслосъемн", "саж", "охлаждающ", "прокладк"),
    "перегрев": ("перегрев", "термостат", "помпа", "радиатор", "вентилятор"),
    "не заводится": ("стартер", "аккумулятор", "искр", "топливн", "иммобилайзер"),
    "плохо заводится": ("стартер", "аккумулятор", "свеч", "топливн"),
    "не держит": ("аккумулятор", "генератор", "утечк", "стартер"),
    "плавает": ("оборот", "рхх", "дроссел", "подсос"),
    "оборот": ("оборот", "рхх", "дроссел"),
    "кондей": ("кондиционер", "фреон", "компрессор"),
    "кондиционер": ("кондиционер", "фреон", "компрессор"),
    "не холодит": ("кондиционер", "фреон", "компрессор"),
    "течет": ("течь", "сальник", "прокладк", "радиатор", "патруб"),
    "масло": ("масл", "масложор", "сальник", "прокладк"),
    "масложор": ("масложор", "маслосъемн", "сальник", "турбин"),
    "запах": ("запах", "горел", "тормозн", "сцеплен", "охлаждающ"),
    "тормоз": ("тормозн", "колодк", "диски", "суппорт", "вакуум"),
    "руль": ("рулев", "рейк", "наконечник", "тяги", "усилитель"),
    "ход": ("подвеск", "амортизатор", "сайлентблок", "шаров"),
    "кочк": ("подвеск", "амортизатор", "стойк", "стабилизатор", "сайлентблок"),
    "яма": ("подвеск", "амортизатор", "стойк", "стабилизатор"),
    "стартер": ("стартер", "втягивающ", "аккумулятор"),
    "аккумулятор": ("аккумулятор", "генератор", "утечк", "заряд"),
    "генератор": ("генератор", "ремень", "диод", "реле"),
    "турбин": ("турбин", "раздув", "давлен", "тяга"),
    "чек": ("ошибк", "лямбда", "катушк", "датчик"),
    "ошибк": ("ошибк", "diag", "сканер", "лямбда"),
    "плавают обороты": ("оборот", "рхх", "дроссел", "подсос"),
    "подтраивает": ("троен", "катушк", "свеч", "форсунк"),
    "не включается": ("акпп", "соленоид", "электрик", "датчик"),
    "закис": ("окисл", "клемм", "масса", "контакт"),
    "плавают": ("оборот", "рхх", "дроссел"),
}


@dataclass
class KnowledgeChunk:
    """Один блок базы знаний."""

    title: str
    text: str
    keywords: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Загрузка и разметка базы знаний
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> set[str]:
    """Токены для сравнения: нормализованные слова длиннее 2 символов."""
    lowered = (text or "").lower().replace("ё", "е")
    words = re.findall(r"[a-zA-Zа-яа-я0-9]+", lowered)
    return {w for w in words if len(w) > 2 and w not in _STOP_WORDS}


# Кэш базы знаний: путь -> (mtime, блоки). перечитываем файл только после правок
_CHUNK_CACHE: dict[str, tuple[float, list[KnowledgeChunk]]] = {}


def load_chunks(path=KNOWLEDGE_BASE_PATH) -> list[KnowledgeChunk]:
    """
    Читает knowledge_base.txt и разбивает на блоки.
    Разделитель блока — строка, начинающаяся с «###».
    """
    try:
        mtime = path.stat().st_mtime
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []

    key = str(path)
    cached = _CHUNK_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]

    chunks: list[KnowledgeChunk] = []
    current_title = "База знаний"
    buffer: list[str] = []

    for line in raw.splitlines():
        if line.strip().startswith("###"):
            if buffer:
                chunks.append(_make_chunk(current_title, "\n".join(buffer).strip()))
                buffer = []
            current_title = line.strip().lstrip("#").strip() or "Без названия"
        else:
            buffer.append(line)

    if buffer:
        chunks.append(_make_chunk(current_title, "\n".join(buffer).strip()))

    result = [chunk for chunk in chunks if chunk.text]
    _CHUNK_CACHE[key] = (mtime, result)
    return result


def _make_chunk(title: str, text: str) -> KnowledgeChunk:
    return KnowledgeChunk(title=title, text=text, keywords=_tokenize(f"{title} {text}"))


# ---------------------------------------------------------------------------
# Поиск релевантных блоков
# ---------------------------------------------------------------------------
def _expand_query(query: str) -> set[str]:
    """Токены запроса + технические синонимы из словаря «народных» фраз."""
    tokens = _tokenize(query)
    lowered = (query or "").lower().replace("ё", "е")

    for phrase, synonyms in _SYNONYMS.items():
        if phrase in lowered:
            tokens.update(synonyms)
            # добавляем и усечённые формы, чтобы ловить «подвеск»/«подвески»
            tokens.update(s[:6] for s in synonyms if len(s) > 4)

    return tokens


def find_relevant(query: str, top_k: int = RAG_TOP_K) -> list[KnowledgeChunk]:
    """Возвращает top_k блоков базы знаний, наиболее близких к запросу."""
    chunks = load_chunks()
    if not chunks:
        return []

    query_tokens = _expand_query(query)
    if not query_tokens:
        # Совсем нечего сопоставить — лучше честно сказать «нужна диагностика»
        return []

    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in chunks:
        score = 0.0
        title_tokens = _tokenize(chunk.title)

        for token in query_tokens:
            for keyword in chunk.keywords:
                if token == keyword:
                    score += 3.0
                elif len(token) >= 5 and (token in keyword or keyword in token):
                    score += 1.5
                elif len(token) >= 4 and keyword.startswith(token[:4]):
                    score += 0.6
            if any(token == t or (len(token) >= 5 and token in t) for t in title_tokens):
                score += 2.0

        # Порог отсекает случайные совпадения по 1-2 буквам
        if score >= 1.5:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]


def build_context(chunks: list[KnowledgeChunk], max_chars: int = 4500) -> str:
    """Склеивает блоки в контекст для промпта, не выходя за лимит символов."""
    parts: list[str] = []
    used = 0
    for chunk in chunks:
        block = f"### {chunk.title}\n{chunk.text}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Промпт и запрос к VedAI
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "Ты — вежливый технический ассистент автосервиса «Магнат Сервис» (г. Минск, "
    "ул. Меньковский тракт, 5, тел. +375 29 888 4777). "
    "Отвечай на русском, коротко и по делу, 4–8 предложений или список из 3–5 пунктов.\n"
    "ПРАВИЛА:\n"
    "1) Опирайся ИСКЛЮЧИТЕЛЬНО на раздел «БАЗА ЗНАНИЙ СЕРВИСА». Если там нет ответа — "
    "честно скажи, что по описанию судить рано, и предложи диагностику.\n"
    "2) Никогда не ставь точный диагноз и не гарантируй ремонт по переписке. "
    "Формулируй как «вероятно», «чаще всего», «похоже на».\n"
    "3) Не выдумывай цены и артикулы. Если цены нет в базе знаний — скажи, "
    "что стоимость назовём после диагностики.\n"
    "4) Не упоминай, что тебе дали базу знаний или контекст.\n"
    "5) В конце одной строкой предложи записаться: «📅 Могу записать на диагностику — "
    "нажмите «Записаться на диагностику» в меню.»\n"
    "6) Не используй markdown-разметку ** и ##; допустимы переносы строк и тире-списки."
)


def build_messages(question: str, chunks: list[KnowledgeChunk]) -> list[dict[str, str]]:
    context = build_context(chunks) or "База знаний не содержит похожих случаев."
    user_prompt = (
        f"БАЗА ЗНАНИЙ СЕРВИСА:\n{context}\n\n"
        f"ВОПРОС КЛИЕНТА: {question}\n\n"
        "Ответь по правилам: вероятная причина (1–3 варианта), что проверить, "
        "чем грозит если откладывать, и предложение записаться на диагностику."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


async def _ask_vedai(messages: list[dict[str, str]]) -> str:
    """Запрос к VedAI Console (OpenAI-совместимый формат). Возвращает текст ответа."""
    headers = {
        "Authorization": f"Bearer {VEDAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VEDAI_MODEL,
        "messages": messages,
        "temperature": VEDAI_TEMPERATURE,
        "max_tokens": VEDAI_MAX_TOKENS,
        "stream": False,
    }

    timeout = aiohttp.ClientTimeout(total=VEDAI_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(VEDAI_API_URL, headers=headers, json=payload) as response:
            raw = await response.text()
            if response.status != 200:
                raise RuntimeError(f"VedAI HTTP {response.status}: {raw[:300]}")
            data = json.loads(raw)

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"VedAI вернул пустой ответ: {raw[:200]}")

    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("VedAI вернул пустой текст ответа")
    return content


def fallback_answer(question: str, chunks: list[KnowledgeChunk]) -> str:
    """Ответ без нейросети: выжимка из базы знаний + приглашение на диагностику."""
    if not chunks:
        return (
            "По вашему описанию ничего однозначно сказать нельзя — такие симптомы "
            "бывают и от мелочи, и от серьёзной причины.\n\n"
            "📅 Приезжайте на диагностику: посмотрим, озвучим причину и стоимость. "
            "Нажмите «Записаться на диагностику» в меню."
        )

    lines = [
        "По вашему описанию чаще всего встречаются такие варианты:",
        "",
    ]
    for chunk in chunks[:2]:
        summary = _summarize(chunk.text)
        lines.append(f"• <b>{chunk.title}</b>")
        for item in summary:
            lines.append(f"  {item}")
        lines.append("")

    lines.append(
        "⚠️ Это вероятные причины по вашему описанию, а не точный диагноз: "
        "нужна диагностика на подъёмнике и считывание ошибок."
    )
    lines.append("")
    lines.append("📅 Могу записать на диагностику — нажмите «Записаться на диагностику» в меню.")
    return "\n".join(lines)


def _summarize(text: str, limit: int = 3) -> list[str]:
    """Берёт первые содержательные строки блока (причины/что проверить)."""
    result: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith(("симптом", "рекоменд", "цен", "ориентиров", "что проверяем")):
            continue
        result.append(line[:160])
        if len(result) >= limit:
            break
    return result or [text[:160]]


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------
async def answer_question(question: str) -> tuple[str, str, list[str]]:
    """
    Главный вход RAG.
    Возвращает: (текст ответа, источник: "vedai" | "knowledge_base", заголовки блоков).
    """
    chunks = find_relevant(question)

    if not VEDAI_API_KEY:
        return fallback_answer(question, chunks), "knowledge_base", [c.title for c in chunks]

    try:
        answer = await _ask_vedai(build_messages(question, chunks))
        return answer, "vedai", [c.title for c in chunks]
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, json.JSONDecodeError):
        return fallback_answer(question, chunks), "knowledge_base", [c.title for c in chunks]
