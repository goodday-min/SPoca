"""책 사진 영어 대화 테스트 (GPT·Claude·Firestore 없이, 가짜로 바꿔 끼워서)"""
import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.core.errors import format_validation_errors
from app.schemas.english import (
    EnglishChatRequest,
    EnglishFinishRequest,
    EnglishScanRequest,
)
from app.services import english_service, llm_service, word_service
from app.services.english_service import END_MARKER, NoTextFoundError

IMG = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
TODAY = date(2026, 10, 6)


def msg(model, payload) -> str:
    try:
        model(**payload)
    except ValidationError as e:
        errs = [{**x, "loc": ("body", *x["loc"])} for x in e.errors()]
        return format_validation_errors(errs)
    raise AssertionError("검증을 통과하면 안 됨")


# ---------- 요청 검증 ----------
def test_scan_accepts_one_to_three_images():
    assert len(EnglishScanRequest(images=[IMG]).images) == 1
    assert len(EnglishScanRequest(images=[IMG] * 3).images) == 3
    for bad in ([], [IMG] * 4, ["hello"], ["data:image/gif;base64,AAAA"], [IMG, "x"]):
        with pytest.raises(ValidationError):
            EnglishScanRequest(images=bad)


def test_chat_request_rules():
    ok = EnglishChatRequest(book_text="Hi.", level="Beginner", messages=[])
    assert ok.messages == []  # 비어 있으면 AI가 먼저
    assert EnglishChatRequest(book_text="Hi.", level="Advanced", messages=[{"role": "user", "content": " hello "}]).messages[0].content == "hello"
    for bad in (
        {"book_text": "", "level": "Beginner"},
        {"book_text": "x", "level": "Expert"},
        {"book_text": "x", "level": "Beginner", "messages": [{"role": "assistant", "content": "hi"}]},  # 마지막이 사용자가 아님
        {"book_text": "x", "level": "Beginner", "messages": [{"role": "user", "content": "  "}]},
        {"book_text": "x", "level": "Beginner", "messages": [{"role": "system", "content": "hi"}]},
        {"book_text": "x", "level": "Beginner", "messages": [{"role": "user", "content": "a" * 1001}]},
        {"book_text": "x" * 8001, "level": "Beginner"},
    ):
        with pytest.raises(ValidationError):
            EnglishChatRequest(**bad)


def test_validation_messages_are_korean():
    assert "난이도" in msg(EnglishChatRequest, {"book_text": "x", "level": "Expert"})
    assert "책 내용" in msg(EnglishChatRequest, {"book_text": "", "level": "Beginner"})


# ---------- 사진 읽기 ----------
def test_parse_sentences_handles_fences_and_junk():
    assert english_service.parse_sentences('```json\n{"sentences": ["A  b.", " ", "C d."]}\n```') == ["A b.", "C d."]
    assert english_service.parse_sentences("no json") == []
    assert english_service.parse_sentences('{"sentences": "x"}') == []
    assert english_service.parse_sentences("[1,2]") == []


def test_join_sentences_respects_limit():
    text, n = english_service.join_sentences(["aaaa", "bbbb", "cccc"], limit=9)
    assert (text, n) == ("aaaa bbbb", 2)


def test_scan_combines_all_pages_in_one_request(monkeypatch):
    seen = {}

    def fake(system, text, images):
        seen["images"] = images
        return json.dumps({"sentences": ["One.", "Two.", "Three."]})

    monkeypatch.setattr(llm_service, "complete_vision", fake)
    r = english_service.scan(EnglishScanRequest(images=[IMG, IMG]))
    assert seen["images"] == [IMG, IMG]
    assert r == {"text": "One. Two. Three.", "sentence_count": 3}


def test_scan_without_text_raises(monkeypatch):
    monkeypatch.setattr(llm_service, "complete_vision", lambda *a: '{"sentences": []}')
    with pytest.raises(NoTextFoundError):
        english_service.scan(EnglishScanRequest(images=[IMG]))


def test_scan_llm_failure_propagates(monkeypatch):
    def boom(*a):
        raise llm_service.LLMError("사진 읽기에 실패했어요")

    monkeypatch.setattr(llm_service, "complete_vision", boom)
    with pytest.raises(llm_service.LLMError):
        english_service.scan(EnglishScanRequest(images=[IMG]))


def test_complete_vision_sends_every_image(monkeypatch):
    import dataclasses
    import io
    import urllib.request

    sent = {}

    class FakeRes(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        sent["body"] = json.loads(req.data)
        return FakeRes(json.dumps({"content": [{"type": "text", "text": "ok"}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm_service, "settings", dataclasses.replace(llm_service.settings, anthropic_api_key="k"))
    llm_service.complete_vision("S", "T", [IMG, IMG, IMG])
    content = sent["body"]["messages"][0]["content"]
    assert [b["type"] for b in content] == ["image", "image", "image", "text"]


# ---------- 대화 ----------
def test_system_prompt_has_level_and_rules():
    b = english_service.build_chat_system("The sea is big.", "Beginner")
    a = english_service.build_chat_system("The sea is big.", "Advanced")
    assert "The sea is big." in b and "100% in English" in b and "Do NOT quiz" in b and END_MARKER in b
    assert "Beginner" in b and "1-2 short sentences" in b and "Advanced" in a and "2-4 sentences" in a
    assert "friend" in b and "NOT a lesson, an interview, or a test" in b and "contractions" in b  # 시험·면접이 아닌 일상 대화 말투


def test_small_talk_first_then_book():
    first = english_service.build_chat_system("Sea.", "Beginner", 0)
    mid = english_service.build_chat_system("Sea.", "Beginner", 2)
    later = english_service.build_chat_system("Sea.", "Beginner", english_service.SMALL_TALK_TURNS)
    assert "Do NOT mention the book yet" in first and "casual greeting" in first
    assert "everyday small talk" in mid and "Do NOT bring up the book yet" in mid
    assert "shift to the book page" in later and "Do NOT" not in later.split("Right now:")[1].split("Still no quizzing")[0]


def test_chat_counts_user_turns_for_phase(monkeypatch):
    seen = {}

    def fake(messages):
        seen["system"] = messages[0]["content"]
        return "ok"

    monkeypatch.setattr(llm_service, "complete", fake)
    english_service.chat(EnglishChatRequest(book_text="B.", level="Beginner", messages=[]))
    assert "Do NOT mention the book yet" in seen["system"]
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}] * 3 + [{"role": "user", "content": "c"}]
    english_service.chat(EnglishChatRequest(book_text="B.", level="Beginner", messages=msgs))
    assert "shift to the book page" in seen["system"]


def test_split_end_marker():
    assert english_service.split_end_marker("Bye now! " + END_MARKER) == ("Bye now!", True)
    assert english_service.split_end_marker("Hello  there?") == ("Hello there?", False)


def test_chat_first_turn_asks_ai_to_start(monkeypatch):
    seen = {}

    def fake(messages):
        seen["m"] = messages
        return "Hi! What did you like about the page?"

    monkeypatch.setattr(llm_service, "complete", fake)
    r = english_service.chat(EnglishChatRequest(book_text="B.", level="Beginner", messages=[]))
    assert r == {"reply": "Hi! What did you like about the page?", "finished": False}
    assert seen["m"][0]["role"] == "system" and seen["m"][-1]["role"] == "user"


def test_chat_passes_history_and_detects_end(monkeypatch):
    seen = {}

    def fake(messages):
        seen["m"] = messages
        return f"Goodbye, see you! {END_MARKER}"

    monkeypatch.setattr(llm_service, "complete", fake)
    req = EnglishChatRequest(
        book_text="B.", level="Advanced",
        messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello"}, {"role": "user", "content": "bye"}],
    )
    r = english_service.chat(req)
    assert r == {"reply": "Goodbye, see you!", "finished": True}
    assert [m["role"] for m in seen["m"]] == ["system", "user", "assistant", "user"]


def test_chat_empty_reply_is_error(monkeypatch):
    monkeypatch.setattr(llm_service, "complete", lambda m: END_MARKER)
    with pytest.raises(llm_service.LLMError):
        english_service.chat(EnglishChatRequest(book_text="B.", level="Beginner", messages=[]))


# ---------- 종료 → 단어 등록 ----------
def test_finish_registers_words_with_english_chat_source(monkeypatch):
    got = {}
    monkeypatch.setattr(
        llm_service, "complete",
        lambda m: json.dumps({"words": [{"word": "vast", "meaning": "광대한", "example": "The sea is vast."}, {"word": "VAST", "meaning": "x"}]}),
    )

    def fake_create_many(entries, registered_date, source, today=None):
        got.update(entries=entries, registered_date=registered_date, source=source)
        return [{"id": "1", **e} for e in entries]

    monkeypatch.setattr(word_service, "create_many", fake_create_many)
    r = english_service.finish(EnglishFinishRequest(book_text="B.", messages=[{"role": "user", "content": "It is vast"}]), TODAY)
    assert r["count"] == 1 and got["source"] == "english_chat" and got["registered_date"] is None  # None → 오늘
    assert got["entries"][0]["word"] == "vast"  # 대소문자만 다른 중복은 합침


def test_finish_caps_at_ten_words(monkeypatch):
    words = [{"word": f"w{i}", "meaning": "m", "example": ""} for i in range(15)]
    monkeypatch.setattr(llm_service, "complete", lambda m: json.dumps({"words": words}))
    monkeypatch.setattr(word_service, "create_many", lambda e, r, source, today=None: [{"id": str(i), **x} for i, x in enumerate(e)])
    r = english_service.finish(EnglishFinishRequest(book_text="B.", messages=[{"role": "user", "content": "hi"}]))
    assert r["count"] == 10


def test_finish_without_user_speech_registers_nothing(monkeypatch):
    def boom(m):
        raise AssertionError("GPT를 부르면 안 됨")

    monkeypatch.setattr(llm_service, "complete", boom)
    assert english_service.finish(EnglishFinishRequest(book_text="B.", messages=[])) == {"count": 0, "items": []}
    assert english_service.finish(EnglishFinishRequest(book_text="B.", messages=[{"role": "assistant", "content": "Hi"}])) == {"count": 0, "items": []}


def test_finish_with_no_words_found_registers_nothing(monkeypatch):
    monkeypatch.setattr(llm_service, "complete", lambda m: '{"words": []}')
    monkeypatch.setattr(word_service, "create_many", lambda *a, **k: (_ for _ in ()).throw(AssertionError("저장하면 안 됨")))
    r = english_service.finish(EnglishFinishRequest(book_text="B.", messages=[{"role": "user", "content": "hi"}]))
    assert r == {"count": 0, "items": []}
