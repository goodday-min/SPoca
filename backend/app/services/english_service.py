"""책 사진 영어 대화. (T4-3)

- scan:   책 사진 1~3장 → Claude(사진 입력) → 인식한 문장들 → 합쳐서 돌려준다 (저장 안 함)
- chat:   책 내용 + 난이도 + 지금까지의 대화 → GPT → AI의 영어 답변 (저장 안 함)
- finish: 책 내용 + 대화 → GPT → 핵심 단어(최대 10개, 한국어 뜻·예문) → 단어장에 자동 등록(source=english_chat)
"""
import json
from datetime import date

from app.schemas.english import (
    BOOK_TEXT_MAX_LENGTH,
    FINISH_MAX_WORDS,
    EnglishChatRequest,
    EnglishFinishRequest,
    EnglishScanRequest,
)
from app.services import llm_service, word_scan_service, word_service

END_MARKER = "[[END]]"
SMALL_TALK_TURNS = 3  # 사용자가 이만큼 말하기 전까지는 책 이야기 없이 일상 대화부터

SCAN_SYSTEM = (
    "You read photos of pages from an English book and extract the readable English text.\n"
    "The photos are consecutive pages. Read them in order and combine them.\n"
    "Return ONLY a JSON object, no explanations, in exactly this shape:\n"
    '{"sentences": ["...", "..."]}\n'
    "Rules:\n"
    "- One English sentence per item, exactly as printed (fix only obvious line-break hyphenation).\n"
    "- Skip page numbers, headers, captions that are not sentences, and non-English text.\n"
    '- If nothing readable, return {"sentences": []}.'
)
SCAN_USER = "Extract the English sentences from these book pages."

LEVEL_RULES = {
    "Beginner": (
        "Level: Beginner. Use easy, common everyday words and short sentences, like talking to a friend who is still "
        "learning English. Reply with 1-2 short sentences. Keep any question very simple."
    ),
    "Advanced": (
        "Level: Advanced. Talk the way native friends do: longer sentences, natural idioms and phrasal verbs, "
        "a richer vocabulary. Reply with 2-4 sentences. Open-ended questions are fine."
    ),
}


def phase_hint(user_turns: int) -> str:
    """대화 흐름 안내. 서버는 대화를 저장하지 않으므로, 사용자가 지금까지 말한 횟수로 단계를 정한다."""
    if user_turns == 0:
        return (
            "Right now: open the chat like friends who just met up. Start with a casual greeting and a light "
            "'how's it going / what've you been up to?' in one or two short lines. Do NOT mention the book yet."
        )
    if user_turns < SMALL_TALK_TURNS:
        return (
            "Right now: keep it everyday small talk (how their day or week is going, plans, mood, food, weather, "
            "hobbies). React to what they said and keep it flowing. Do NOT bring up the book yet unless they do."
        )
    return (
        "Right now: small talk has warmed up, so smoothly shift to the book page if you haven't yet, the way a friend "
        "would ('Oh, by the way, I was reading something about ...' or 'That reminds me of what's on this page...'). "
        "Chat about it casually and connect it to their life; don't recite it. Still no quizzing."
    )


def build_chat_system(book_text: str, level: str, user_turns: int = 0) -> str:
    return (
        "You are the user's easygoing friend chatting in English. This is a relaxed, everyday conversation, "
        "NOT a lesson, an interview, or a test. The user has a book page with them (below). Like real friends, you "
        "start with greetings and everyday small talk first, and only later move on to the book.\n"
        "How to sound:\n"
        "- Talk like a real friend texting or chatting over coffee: warm, curious, a bit playful. Use contractions "
        "(I'm, it's, don't), casual reactions (Oh nice, Haha, Yeah, Really?, No way), and share your own little "
        "opinions or stories too, so it isn't one-sided.\n"
        "- Speak 100% in English, even if the user writes in Korean (just keep chatting in English, gently).\n"
        "- Do NOT quiz the user, check their understanding, or ask for right answers. Never sound like a teacher, "
        "an interviewer, a customer-service agent or an assistant (no 'Great question!', no 'I'd be happy to', "
        "no formal phrasing like 'Which ... did you find most interesting').\n"
        "- React to what they actually said first, then maybe add a thought. Ask a question only some of the time, "
        "and never more than one.\n"
        "- No lists, bullet points, markdown or emojis (your words are read aloud).\n"
        f"- {LEVEL_RULES[level]}\n"
        "- If the user's English has a small mistake, just answer naturally using the correct form; never lecture.\n"
        "- If the chat has reached a natural ending, or the user says goodbye, say a warm, short goodbye like a friend "
        f"would, and put the exact marker {END_MARKER} at the very end of that message. Never use the marker otherwise.\n\n"
        f"{phase_hint(user_turns)}\n\n"
        f"[Book page]\n{book_text}"
    )


FINISH_SYSTEM = (
    "You help an English learner build a vocabulary list from a book page and a conversation about it.\n"
    f"Pick up to {FINISH_MAX_WORDS} key vocabulary words or short phrases worth learning, "
    "taken from the book content or used in the conversation. Skip very easy words (the, is, and, ...) and proper names.\n"
    "Return ONLY a JSON object, no explanations, in exactly this shape:\n"
    '{"words": [{"word": "...", "meaning": "...", "example": "..."}]}\n'
    "Rules:\n"
    "- word: the English word or phrase (base form is fine).\n"
    "- meaning: a short natural Korean meaning (a few words) that fits how it is used.\n"
    "- example: a short English example sentence taken from the book or the conversation.\n"
    '- If there is nothing worth learning, return {"words": []}.'
)


class NoTextFoundError(Exception):
    """사진에서 읽을 수 있는 영어 글을 찾지 못했을 때"""


def parse_sentences(text: str) -> list[str]:
    """Claude 답변(JSON 글자)에서 문장 목록을 꺼낸다. JSON이 아니거나 비었으면 빈 목록."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    raw = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        s = " ".join(str(s or "").split())
        if s:
            out.append(s)
    return out


def join_sentences(sentences: list[str], limit: int = BOOK_TEXT_MAX_LENGTH) -> tuple[str, int]:
    """문장들을 공백으로 이어 붙이되 글자 수 한도를 넘기지 않는다. (본문, 들어간 문장 수)"""
    parts, total = [], 0
    for s in sentences:
        add = len(s) + (1 if parts else 0)
        if total + add > limit:
            break
        parts.append(s)
        total += add
    return " ".join(parts), len(parts)


def scan(payload: EnglishScanRequest) -> dict:
    answer = llm_service.complete_vision(SCAN_SYSTEM, SCAN_USER, payload.images)  # 실패하면 LLMError
    text, count = join_sentences(parse_sentences(answer))
    if count == 0:
        raise NoTextFoundError()
    return {"text": text, "sentence_count": count}


def split_end_marker(reply: str) -> tuple[str, bool]:
    """답변 끝의 종료 표시를 떼어 낸다. (표시를 뺀 답변, 종료 여부)"""
    finished = END_MARKER in reply
    clean = " ".join(reply.replace(END_MARKER, " ").split())
    return clean, finished


def chat(req: EnglishChatRequest) -> dict:
    user_turns = sum(1 for m in req.messages if m.role == "user")
    messages = [{"role": "system", "content": build_chat_system(req.book_text, req.level, user_turns)}]
    messages += [{"role": m.role, "content": m.content} for m in req.messages]
    if not req.messages:  # AI가 먼저 말을 거는 첫 턴
        messages.append({"role": "user", "content": "(Please start the conversation.)"})
    reply, finished = split_end_marker(llm_service.complete(messages))  # 실패하면 LLMError
    if not reply:
        raise llm_service.LLMError("GPT가 빈 답변을 보냈어요")
    return {"reply": reply, "finished": finished}


def _transcript(req: EnglishFinishRequest) -> str:
    return "\n".join(f"{'User' if m.role == 'user' else 'Partner'}: {m.content}" for m in req.messages)


def finish(req: EnglishFinishRequest, today: date | None = None) -> dict:
    # 사용자가 한 번도 말하지 않았으면 뽑을 단어도 없다 (등록 없이 끝)
    if not any(m.role == "user" for m in req.messages):
        return {"count": 0, "items": []}
    user = f"[Book content]\n{req.book_text}\n\n[Conversation]\n{_transcript(req)}"
    answer = llm_service.complete([{"role": "system", "content": FINISH_SYSTEM}, {"role": "user", "content": user}])
    entries = word_scan_service.parse_words(answer, limit=FINISH_MAX_WORDS)
    if not entries:
        return {"count": 0, "items": []}
    items = word_service.create_many(entries, None, source="english_chat", today=today)  # 등록일 = 오늘
    return {"count": len(items), "items": items}
