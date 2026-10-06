"""채팅 단위 테스트 (Firestore·GPT 없이): 프롬프트 만들기, 요청 검증"""
from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.services.chat_service import build_system_prompt

SUMMARY = {
    "today": "2026-10-05",
    "overall": {"period": {"start": "2026-05-28", "end": "2026-10-04"}, "count": 110, "average": 7.1, "max": 14, "min": 2},
    "recent_7d": {
        "period": {"start": "2026-09-28", "end": "2026-10-04"}, "count": 7, "average": 10.7, "max": 13, "min": 8,
        "previous_average": 9.7, "trend": "증가",
    },
}
EMPTY = {
    "today": "2026-10-05",
    "overall": {"period": {"start": None, "end": None}, "count": 0, "average": None, "max": None, "min": None},
    "recent_7d": {"period": {"start": "2026-09-28", "end": "2026-10-04"}, "count": 0, "average": None, "max": None,
                  "min": None, "previous_average": None, "trend": "비교 불가"},
}


def test_prompt_contains_numbers():
    p = build_system_prompt(SUMMARY)
    for s in ["110일", "7.1개", "10.7개", "9.7개", "증가", "2026-09-28 ~ 2026-10-04"]:
        assert s in p, s


def test_prompt_empty_data():
    p = build_system_prompt(EMPTY)
    assert "기록 없음" in p and "없음" in p and "비교 불가" in p


def test_request_validation():
    assert ChatRequest(message="  안녕  ").message == "안녕"
    for bad in ["", "   ", "x" * 4001]:
        try:
            ChatRequest(message=bad)
        except ValidationError:
            continue
        raise AssertionError(bad)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("통과:", name)
    print("모두 통과")


def test_prompt_lists_daily_values_including_today():
    from datetime import date
    from app.services.summary_service import build_summary

    t = date(2026, 10, 6)
    s = build_summary([{"date": "2026-10-06", "value": 2}, {"date": "2026-10-04", "value": 9}], t)
    p = build_system_prompt(s)
    assert "2026-10-06 (오늘): 2개" in p
    assert "2026-10-04: 9개" in p
    assert "2026-10-05: 기록 없음" in p
