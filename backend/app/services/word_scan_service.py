"""책 사진 한 장에서 단어를 읽어 단어장에 등록한다. (T3-4)

흐름: 사진 → Claude(Anthropic 호환 주소, 사진 입력) → JSON 단어 목록 → 정리(중복·길이·개수) → 한 번에 등록.
뜻이 사진에 인쇄돼 있으면 그대로 쓰고, 없으면 AI가 짧은 한국어 뜻을 채운다(AI가 만든 뜻이라 틀릴 수 있어 단어장에서 고칠 수 있다).
"""
import json
import re
from datetime import date

from app.schemas.word import (
    EXAMPLE_MAX_LENGTH,
    MEANING_MAX_LENGTH,
    SCAN_MAX_WORDS,
    WORD_MAX_LENGTH,
    WordScanRequest,
)
from app.services import llm_service, word_service

SYSTEM_PROMPT = (
    "You read a photo of a page from an English vocabulary book and extract its vocabulary entries.\n"
    "Return ONLY a JSON object, no explanations, in exactly this shape:\n"
    '{"words": [{"word": "...", "meaning": "...", "example": "..."}]}\n'
    "Rules:\n"
    "- word: the English word or phrase exactly as printed.\n"
    "- meaning: if a meaning is printed next to the word, copy it exactly (keep its original language). "
    "If no meaning is printed, write a short natural Korean meaning yourself (a few words, e.g. \"회복력 있는\"). "
    "If an example sentence is printed, choose the sense that fits that sentence.\n"
    "- example: copy the example sentence only if it is printed. Otherwise use an empty string.\n"
    '- If the photo has no readable vocabulary, return {"words": []}.'
)


class NoWordsFoundError(Exception):
    """사진에서 단어를 하나도 찾지 못했을 때"""


USER_TEXT = "Extract the vocabulary from this page."


def parse_words(text: str, limit: int = SCAN_MAX_WORDS) -> list[dict]:
    """GPT 답변(JSON 글자)을 단어 목록으로 정리한다.

    - ```json 코드 블록이나 앞뒤 설명이 붙어도 JSON 부분만 꺼낸다.
    - 단어가 비었거나 너무 길면 버리고, 뜻·예문이 길면 잘라낸다.
    - 같은 단어(대소문자 무시)는 처음 것만 남기고, 최대 limit개까지만 쓴다.
    - JSON이 아니면 빈 목록.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    raw = data.get("words") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []

    result, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        word = re.sub(r"\s+", " ", str(item.get("word") or "")).strip()
        if not word or len(word) > WORD_MAX_LENGTH:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "word": word,
                "meaning": str(item.get("meaning") or "").strip()[:MEANING_MAX_LENGTH],
                "example": str(item.get("example") or "").strip()[:EXAMPLE_MAX_LENGTH],
            }
        )
        if len(result) >= limit:
            break
    return result


def scan(payload: WordScanRequest, today: date | None = None) -> dict:
    today = today or word_service.today_kst()
    # 등록일이 잘못됐으면 GPT를 부르기 전에 먼저 거부한다.
    word_service.check_registered_date(payload.registered_date, today)
    text = llm_service.complete_vision(SYSTEM_PROMPT, USER_TEXT, payload.image)  # 실패하면 LLMError
    entries = parse_words(text)
    if not entries:
        raise NoWordsFoundError()
    items = word_service.create_many(entries, payload.registered_date, source="scan", today=today)
    return {"count": len(items), "items": items}
