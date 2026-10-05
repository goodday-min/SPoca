"""요약 계산 시험. Firestore 없이 계산 규칙만 확인한다.

실행 (backend 폴더에서): python -m tests.test_summary
"""
from datetime import date, timedelta

from app.services.summary_service import build_summary

TODAY = date(2026, 10, 5)  # 최근 7일(오늘 포함) = 9/29~10/5, 이전 7일 = 9/22~9/28


def rec(day: date, value: int) -> dict:
    return {"date": day.isoformat(), "value": value}


def days(values: list[int], start: date) -> list[dict]:
    return [rec(start + timedelta(days=i), v) for i, v in enumerate(values)]


def test_empty():
    s = build_summary([], TODAY)
    assert s["overall"]["count"] == 0 and s["overall"]["average"] is None
    assert s["overall"]["period"] == {"start": None, "end": None}
    assert s["recent_7d"]["trend"] == "비교 불가"


def test_windows_and_stats():
    prev = days([10] * 7, date(2026, 9, 22))
    recent = days([12, 14, 11, 13, 12, 12, 12], date(2026, 9, 29))  # 마지막 값(10/5)은 오늘
    old = [rec(date(2026, 6, 1), 2)]
    s = build_summary(old + prev + recent + [rec(date(2026, 9, 21), 99)], TODAY)  # 이전 7일보다 앞선 기록은 둘 다 안 들어간다
    r = s["recent_7d"]
    assert r["period"] == {"start": "2026-09-29", "end": "2026-10-05"}
    assert r["count"] == 7 and r["average"] == 12.3 and r["max"] == 14 and r["min"] == 11
    assert r["previous_average"] == 10.0 and r["trend"] == "증가"
    o = s["overall"]
    assert o["count"] == 16 and o["max"] == 99 and o["min"] == 2
    assert o["period"] == {"start": "2026-06-01", "end": "2026-10-05"}


def test_today_is_included():
    s = build_summary([rec(TODAY, 8), rec(TODAY - timedelta(days=6), 4), rec(TODAY - timedelta(days=7), 100)], TODAY)
    r = s["recent_7d"]
    assert r["count"] == 2 and r["average"] == 6.0  # 오늘과 6일 전은 포함, 7일 전은 제외
    assert r["previous_average"] == 100.0


def test_exactly_ten_percent_is_keep():
    prev = days([10] * 7, date(2026, 9, 22))
    recent = days([11] * 7, date(2026, 9, 29))
    assert build_summary(prev + recent, TODAY)["recent_7d"]["trend"] == "유지"
    recent_low = days([9] * 7, date(2026, 9, 29))
    assert build_summary(prev + recent_low, TODAY)["recent_7d"]["trend"] == "유지"


def test_decrease():
    prev = days([10] * 7, date(2026, 9, 22))
    recent = days([8] * 7, date(2026, 9, 29))
    assert build_summary(prev + recent, TODAY)["recent_7d"]["trend"] == "감소"


def test_cannot_compare():
    recent = days([8] * 7, date(2026, 9, 29))
    assert build_summary(recent, TODAY)["recent_7d"]["trend"] == "비교 불가"  # 이전 7일 기록 없음
    prev_zero = days([0] * 7, date(2026, 9, 22))
    assert build_summary(prev_zero + recent, TODAY)["recent_7d"]["trend"] == "비교 불가"  # 이전 평균 0
    prev = days([10] * 7, date(2026, 9, 22))
    assert build_summary(prev, TODAY)["recent_7d"]["trend"] == "비교 불가"  # 최근 7일 기록 없음


def test_rest_days_not_counted_as_zero():
    # 7일 중 3일만 기록: 평균은 기록 있는 날만으로 계산한다.
    recent = [rec(date(2026, 9, 29), 6), rec(date(2026, 9, 30), 9), rec(date(2026, 10, 3), 12)]
    r = build_summary(recent, TODAY)["recent_7d"]
    assert r["count"] == 3 and r["average"] == 9.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("통과:", t.__name__)
    print(f"{len(tests)}개 모두 통과")
