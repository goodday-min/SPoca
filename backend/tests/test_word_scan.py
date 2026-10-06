"""책 사진 스캔 등록 테스트 (GPT·Firestore 없이, 가짜로 바꿔 끼워서)"""
import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.core.errors import format_validation_errors
from app.schemas.word import WordScanRequest
from app.services import llm_service, word_scan_service, word_service
from app.services.word_scan_service import SYSTEM_PROMPT, USER_TEXT, NoWordsFoundError, parse_words

TODAY = date(2026, 10, 6)
IMG = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="


def msg(payload) -> str:
    try:
        WordScanRequest(**payload)
    except ValidationError as e:
        errs = [{**x, "loc": ("body", *x["loc"])} for x in e.errors()]
        return format_validation_errors(errs)
    raise AssertionError("검증을 통과하면 안 됨")


def test_prompt_copies_printed_meaning_else_asks_for_korean_meaning():
    assert "copy it exactly" in SYSTEM_PROMPT and "short natural Korean meaning" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT and USER_TEXT


def test_vision_request_shape_and_errors():
    import io
    import urllib.request

    sent = {}

    class FakeRes(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        sent["url"], sent["headers"], sent["body"] = req.full_url, dict(req.header_items()), json.loads(req.data)
        return FakeRes(json.dumps({"content": [{"type": "text", "text": '{"words": []}'}]}).encode())

    old_urlopen, old_key = urllib.request.urlopen, llm_service.settings
    urllib.request.urlopen = fake_urlopen
    try:
        # 설정은 바꿀 수 없는(frozen) 객체라 같은 값에 키만 채운 복사본으로 바꿔 끼운다
        import dataclasses

        llm_service.settings = dataclasses.replace(old_key, anthropic_api_key="k", anthropic_base_url="https://x/v1")
        assert llm_service.complete_vision("SYS", "TXT", IMG) == '{"words": []}'
        llm_service.settings = dataclasses.replace(old_key, anthropic_api_key="")
        with pytest.raises(llm_service.LLMError):
            llm_service.complete_vision("SYS", "TXT", IMG)
    finally:
        urllib.request.urlopen, llm_service.settings = old_urlopen, old_key
    assert sent["url"] == "https://x/v1/messages"
    assert sent["headers"]["X-api-key"] == "k"
    block = sent["body"]["messages"][0]["content"][0]
    assert block == {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "/9j/4AAQSkZJRg=="}}
    assert sent["body"]["system"] == "SYS" and sent["body"]["max_tokens"] > 0


def test_parse_plain_and_fenced_json():
    plain = json.dumps({"words": [{"word": "apple", "meaning": "사과", "example": "An apple."}]})
    assert parse_words(plain) == [{"word": "apple", "meaning": "사과", "example": "An apple."}]
    fenced = "여기 결과예요:\n```json\n" + plain + "\n```"
    assert parse_words(fenced)[0]["word"] == "apple"


def test_meaning_may_be_missing_or_null():
    out = parse_words('{"words": [{"word": "pear"}, {"word": "plum", "meaning": null, "example": null}]}')
    assert out == [{"word": "pear", "meaning": "", "example": ""}, {"word": "plum", "meaning": "", "example": ""}]


def test_duplicates_in_one_scan_are_merged_ignoring_case():
    out = parse_words('{"words": [{"word": "Apple"}, {"word": "apple"}, {"word": " APPLE "}, {"word": "pear"}]}')
    assert [x["word"] for x in out] == ["Apple", "pear"]  # 처음 것만 남긴다


def test_limit_50_and_long_values():
    many = {"words": [{"word": f"w{i}"} for i in range(80)]}
    assert len(parse_words(json.dumps(many))) == 50
    out = parse_words(json.dumps({"words": [{"word": "a", "meaning": "가" * 300, "example": "x" * 500}, {"word": "b" * 51}]}))
    assert len(out) == 1  # 51자 단어는 버림
    assert len(out[0]["meaning"]) == 200 and len(out[0]["example"]) == 300


def test_bad_answers_give_empty_list():
    for bad in ["", "단어를 못 찾았어요", "{not json}", '{"words": "x"}', "[]", '{"words": [1, "a", null]}']:
        assert parse_words(bad) == []


def test_request_validation():
    assert msg({"image": "hello"}) == "사진: JPEG·PNG·WebP 사진만 올릴 수 있어요"
    assert msg({"image": "data:application/pdf;base64,AAAA"}) == "사진: JPEG·PNG·WebP 사진만 올릴 수 있어요"
    assert msg({"image": "data:image/png;base64," + "A" * 7_000_000}) == "사진: 사진이 너무 커요. 더 작게 줄여서 올려 주세요"
    assert msg({}) == "사진: 꼭 필요해요"
    assert msg({"image": IMG, "registered_date": "2026-13-45"}).startswith("등록일: 존재하지 않는 날짜예요")
    assert WordScanRequest(image=IMG, registered_date="2026-10-08").registered_date == "2026-10-08"


def fake(monkeypatch_target, name, fn):
    old = getattr(monkeypatch_target, name)
    setattr(monkeypatch_target, name, fn)
    return lambda: setattr(monkeypatch_target, name, old)


def test_scan_registers_found_words_with_scan_source():
    saved = {}

    def fake_create_many(entries, registered_date, source, today=None):
        saved.update(entries=entries, registered_date=registered_date, source=source)
        return [{"id": str(i), **e} for i, e in enumerate(entries)]

    undo = [
        fake(llm_service, "complete_vision", lambda system, text, image: '{"words": [{"word": "apple", "meaning": "사과"}, {"word": "pear"}]}'),
        fake(word_service, "create_many", fake_create_many),
    ]
    try:
        out = word_scan_service.scan(WordScanRequest(image=IMG, registered_date="2026-10-09"), TODAY)
    finally:
        for u in undo:
            u()
    assert out["count"] == 2
    assert saved["source"] == "scan" and saved["registered_date"] == "2026-10-09"
    assert [e["word"] for e in saved["entries"]] == ["apple", "pear"]


def test_scan_rejects_past_date_before_calling_gpt():
    called = []
    undo = fake(llm_service, "complete_vision", lambda system, text, image: called.append(1) or "{}")
    try:
        with pytest.raises(word_service.PastRegisteredDateError):
            word_scan_service.scan(WordScanRequest(image=IMG, registered_date="2026-10-01"), TODAY)
    finally:
        undo()
    assert called == []  # 등록일이 잘못이면 GPT 비용을 쓰지 않는다


def test_scan_with_no_words_raises_and_saves_nothing():
    saved = []
    undo = [
        fake(llm_service, "complete_vision", lambda system, text, image: '{"words": []}'),
        fake(word_service, "create_many", lambda *a, **k: saved.append(1)),
    ]
    try:
        with pytest.raises(NoWordsFoundError):
            word_scan_service.scan(WordScanRequest(image=IMG), TODAY)
    finally:
        for u in undo:
            u()
    assert saved == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("통과:", name)
    print("모두 통과")
