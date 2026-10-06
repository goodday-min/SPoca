"""단어(words) 스키마·새 단어 문서 테스트 (Firestore 없이)"""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.errors import format_validation_errors
from app.schemas.word import STAGE_OFFSET_DAYS, STAGES, WordCreate, WordUpdate
from app.services.word_service import PastRegisteredDateError, check_registered_date, new_word_doc, sort_items

TODAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc)


def msg(payload) -> str:
    try:
        WordCreate(**payload)
    except ValidationError as e:
        errs = [{**x, "loc": ("body", *x["loc"])} for x in e.errors()]
        return format_validation_errors(errs)
    raise AssertionError("검증을 통과하면 안 됨")


def test_new_word_starts_as_new_and_reviewing():
    doc = new_word_doc(WordCreate(word="resilient", meaning="회복력 있는", example="She is resilient."), "manual", TODAY, NOW)
    assert doc == {
        "word": "resilient",
        "meaning": "회복력 있는",
        "example": "She is resilient.",
        "registered_date": "2026-10-06",  # 등록일을 안 보내면 오늘
        "stage": "New",
        "status": "reviewing",
        "source": "manual",
        "passed_stage": None,
        "reviewed_at": None,
        "created_at": NOW,
    }


def test_registered_date_is_kept_and_meaning_can_be_empty():
    doc = new_word_doc(WordCreate(word="apple", registered_date="2026-10-09"), "scan", TODAY)
    assert doc["registered_date"] == "2026-10-09"
    assert doc["meaning"] == "" and doc["example"] == ""
    assert doc["source"] == "scan"


def test_spaces_are_trimmed_and_blank_word_is_rejected():
    assert WordCreate(word="  apple  ", meaning=" 사과 ").word == "apple"
    assert WordCreate(word="apple", meaning=" 사과 ").meaning == "사과"
    assert msg({"word": "   "}) == "단어: 비워 둘 수 없어요"
    assert msg({}) == "단어: 꼭 필요해요"


def test_length_limits():
    assert msg({"word": "a" * 51}) == "단어: 50자 이하로 입력해 주세요"
    assert msg({"word": "a", "meaning": "가" * 201}) == "뜻: 200자 이하로 입력해 주세요"
    assert msg({"word": "a", "example": "x" * 301}) == "예문: 300자 이하로 입력해 주세요"
    WordCreate(word="a" * 50, meaning="가" * 200, example="x" * 300)  # 경계값은 통과


def test_registered_date_validation():
    assert msg({"word": "a", "registered_date": "2026-13-45"}) == "등록일: 존재하지 않는 날짜예요. YYYY-MM-DD 형식으로 입력해 주세요."
    assert msg({"word": "a", "registered_date": "20261006"}) == "등록일: YYYY-MM-DD 형식으로 입력해 주세요"


def test_duplicate_words_are_allowed():
    a = new_word_doc(WordCreate(word="apple"), "manual", TODAY)
    b = new_word_doc(WordCreate(word="apple"), "scan", TODAY)
    assert a["word"] == b["word"]  # 같은 단어를 두 번 만들 수 있다


def test_past_registered_date_is_rejected_but_today_and_future_pass():
    check_registered_date(None, TODAY)  # 비우면 오늘이라 통과
    check_registered_date("2026-10-06", TODAY)  # 오늘
    check_registered_date("2026-10-07", TODAY)  # 내일
    check_registered_date("2027-01-01", TODAY)  # 먼 미래
    with pytest.raises(PastRegisteredDateError):
        check_registered_date("2026-10-05", TODAY)  # 어제
    with pytest.raises(PastRegisteredDateError):
        check_registered_date("2020-01-01", TODAY)


def w(id, word, reg, stage="New", status="reviewing", hour=0):
    return {"id": id, "word": word, "registered_date": reg, "stage": stage, "status": status,
            "created_at": datetime(2026, 10, 6, hour, 0, tzinfo=timezone.utc)}


def ids(items):
    return [x["id"] for x in items]


def test_sort_latest_registered_first_then_latest_created():
    items = [
        w("a", "a", "2026-10-06", hour=1),
        w("b", "b", "2026-10-09", hour=0),  # 미래 등록일 → 맨 위
        w("c", "c", "2026-10-06", hour=5),  # a 와 같은 날, 더 늦게 만듦 → a 보다 위
        w("d", "d", "2026-10-01", hour=9),
    ]
    assert ids(sort_items(items, "latest")) == ["b", "c", "a", "d"]


def test_old_docs_without_created_at_count_as_oldest():
    old = {"id": "old", "word": "o", "registered_date": "2026-10-06", "stage": "New", "status": "reviewing"}
    assert ids(sort_items([old, w("n", "n", "2026-10-06", hour=1)], "latest")) == ["n", "old"]


def test_sort_by_stage_with_finished_words_last():
    items = [
        w("m", "m", "2026-09-01", stage="Master"),
        w("n1", "n1", "2026-10-01", stage="New", hour=1),
        w("v2", "v2", "2026-10-02", stage="V2"),
        w("n2", "n2", "2026-10-05", stage="New", hour=1),  # 같은 New 안에서는 등록일 나중이 먼저
        w("v1", "v1", "2026-10-03", stage="V1"),
        w("done", "done", "2026-10-06", stage="V3", status="passed"),
        w("fail", "fail", "2026-10-04", stage="Master", status="failed"),
    ]
    # 복습 중 단어를 단계순으로, 끝난 단어(외움·못 외움)는 맨 아래(등록일 나중이 먼저)
    assert ids(sort_items(items, "stage")) == ["n2", "n1", "v1", "v2", "m", "done", "fail"]


def test_update_takes_only_word_meaning_example():
    u = WordUpdate(word=" apple ", meaning="사과", example="", stage="Master", status="passed", registered_date="2020-01-01")
    assert u.model_dump() == {"word": "apple", "meaning": "사과", "example": ""}  # 단계·상태·등록일은 버려진다
    assert msg_update({"word": ""}) == "단어: 비워 둘 수 없어요"


def msg_update(payload) -> str:
    try:
        WordUpdate(**payload)
    except ValidationError as e:
        errs = [{**x, "loc": ("body", *x["loc"])} for x in e.errors()]
        return format_validation_errors(errs)
    raise AssertionError("검증을 통과하면 안 됨")


def test_stage_schedule_matches_prd():
    assert STAGES == ("New", "V1", "V2", "V3", "Master")
    assert [STAGE_OFFSET_DAYS[s] for s in STAGES] == [0, 1, 3, 7, 30]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("통과:", name)
    print("모두 통과")
