"""학습 통계 단위 테스트 (Firestore 없이): 최장 연속 기록, 요일별 평균"""
from app.services.statistics_service import build_statistics


def rec(d, v):
    return {"date": d, "value": v}


def test_empty():
    s = build_statistics([])
    assert s["longest_streak"] == {"days": 0, "start": None, "end": None}
    assert s["best_weekday"] is None
    assert len(s["weekday_average"]) == 7 and all(w["average"] is None and w["count"] == 0 for w in s["weekday_average"])
    assert [w["weekday"] for w in s["weekday_average"]] == ["월", "화", "수", "목", "금", "토", "일"]


def test_longest_streak_and_gap():
    # 10/1~10/3 (3일) → 10/4 없음 → 10/5~10/9 (5일)
    days = [f"2026-10-0{d}" for d in (1, 2, 3, 5, 6, 7, 8, 9)]
    s = build_statistics([rec(d, 1) for d in days])
    assert s["longest_streak"] == {"days": 5, "start": "2026-10-05", "end": "2026-10-09"}


def test_zero_value_day_still_counts_as_record():
    s = build_statistics([rec("2026-10-01", 5), rec("2026-10-02", 0), rec("2026-10-03", 4)])
    assert s["longest_streak"]["days"] == 3


def test_tie_prefers_latest_and_month_boundary():
    # 9/29~10/1 (3일, 월 경계 넘음) 과 10/5~10/7 (3일) → 같으면 더 최근
    days = ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-05", "2026-10-06", "2026-10-07"]
    s = build_statistics([rec(d, 1) for d in days])
    assert s["longest_streak"] == {"days": 3, "start": "2026-10-05", "end": "2026-10-07"}
    assert build_statistics([rec(d, 1) for d in days[:3]])["longest_streak"]["start"] == "2026-09-29"


def test_weekday_average_only_days_with_records():
    # 2026-10-05 = 월, 10-12 = 월, 10-09 = 금
    s = build_statistics([rec("2026-10-05", 10), rec("2026-10-12", 5), rec("2026-10-09", 20)])
    by = {w["weekday"]: w for w in s["weekday_average"]}
    assert by["월"] == {"weekday": "월", "average": 7.5, "count": 2}
    assert by["금"]["average"] == 20.0 and by["화"]["average"] is None and by["화"]["count"] == 0
    assert s["best_weekday"] == "금"


def test_best_weekday_tie_picks_earlier_and_zero_average_counts():
    s = build_statistics([rec("2026-10-06", 8), rec("2026-10-08", 8)])  # 화, 목 동점
    assert s["best_weekday"] == "화"
    z = build_statistics([rec("2026-10-06", 0)])
    assert z["best_weekday"] == "화" and z["weekday_average"][1]["average"] == 0.0


def test_period_is_echoed():
    s = build_statistics([], "2026-10-01", "2026-10-31")
    assert s["period"] == {"start": "2026-10-01", "end": "2026-10-31"}
