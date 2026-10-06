"""리포트 단위 테스트 (Firestore 없이): 7일 / 월별 / 전체, 단계 분포"""
from datetime import date, timedelta

import pytest

from app.services.report_service import InvalidMonthError, build_report, parse_month, stage_distribution

TODAY = date(2026, 10, 6)


def rec(d, v):
    return {"date": d.isoformat() if isinstance(d, date) else d, "value": v}


def w(stage, status="reviewing"):
    return {"stage": stage, "status": status}


def test_7d_has_trend_and_seven_days_with_gaps():
    recs = [rec(TODAY, 2), rec(TODAY - timedelta(days=2), 9)] + [rec(TODAY - timedelta(days=7 + i), 4) for i in range(3)]
    r = build_report(recs, [], "7d", None, TODAY)
    assert r["period"] == "7d" and r["month"] is None
    assert [d["date"] for d in r["daily"]][0] == "2026-09-30" and r["daily"][-1] == {"date": "2026-10-06", "value": 2}
    assert len(r["daily"]) == 7 and r["daily"][3]["value"] is None and r["daily"][4]["value"] == 9  # 10/3 기록 없음 → 빈 칸
    s = r["summary"]
    assert s["count"] == 2 and s["average"] == 5.5 and s["max"] == 9 and s["min"] == 2
    assert s["period"] == {"start": "2026-09-30", "end": "2026-10-06"}
    assert s["previous_average"] == 4.0 and s["trend"] == "증가"


def test_month_covers_every_day_and_has_no_trend():
    recs = [rec("2026-10-01", 4), rec("2026-10-06", 6), rec("2026-09-30", 100)]
    r = build_report(recs, [], "month", "2026-10", TODAY)
    assert r["month"] == "2026-10" and len(r["daily"]) == 31  # 오늘 이후도 말일까지
    assert r["daily"][0] == {"date": "2026-10-01", "value": 4} and r["daily"][-1] == {"date": "2026-10-31", "value": None}
    s = r["summary"]
    assert s["count"] == 2 and s["average"] == 5.0 and s["max"] == 6 and s["min"] == 4  # 9/30 기록은 제외
    assert s["period"] == {"start": "2026-10-01", "end": "2026-10-31"}
    assert s["trend"] is None and s["previous_average"] is None


def test_month_lengths_including_leap_february():
    assert len(build_report([], [], "month", "2028-02", TODAY)["daily"]) == 29
    assert len(build_report([], [], "month", "2026-02", TODAY)["daily"]) == 28
    assert len(build_report([], [], "month", "2026-04", TODAY)["daily"]) == 30


def test_month_without_records_is_empty_summary_with_blank_graph():
    r = build_report([rec("2026-10-01", 4)], [], "month", "2026-05", TODAY)
    s = r["summary"]
    assert s["count"] == 0 and s["average"] is None and s["max"] is None and s["min"] is None
    assert len(r["daily"]) == 31 and all(d["value"] is None for d in r["daily"])


def test_all_lists_only_recorded_days_in_date_order():
    recs = [rec("2026-10-06", 2), rec("2026-05-28", 7), rec("2026-08-01", 0)]
    r = build_report(recs, [], "all", None, TODAY)
    assert [d["date"] for d in r["daily"]] == ["2026-05-28", "2026-08-01", "2026-10-06"]
    s = r["summary"]
    assert s["count"] == 3 and s["average"] == 3.0 and s["max"] == 7 and s["min"] == 0
    assert s["period"] == {"start": "2026-05-28", "end": "2026-10-06"} and s["trend"] is None


def test_all_without_records():
    r = build_report([], [], "all", None, TODAY)
    assert r["daily"] == [] and r["summary"]["count"] == 0 and r["summary"]["period"] == {"start": None, "end": None}


def test_stage_distribution_counts_reviewing_and_finished():
    words = [w("New"), w("New"), w("V2"), w("Master"), w("V1", "passed"), w("Master", "passed"), w("Master", "failed")]
    d = stage_distribution(words)
    assert d["reviewing"] == {"New": 2, "V1": 0, "V2": 1, "V3": 0, "Master": 1}
    assert d["finished"] == {"passed": 2, "failed": 1}  # 끝난 단어의 단계는 분포에 안 센다


def test_distribution_is_same_for_every_period():
    words = [w("V3")]
    for p, m in (("7d", None), ("month", "2026-10"), ("all", None)):
        assert build_report([], words, p, m, TODAY)["stage_distribution"]["reviewing"]["V3"] == 1


def test_parse_month():
    assert parse_month("2026-10") == (2026, 10)
    for bad in ["2026-13", "2026-1", "26-10", "abcd-ef", "2026-00", "2026/10"]:
        with pytest.raises(InvalidMonthError):
            parse_month(bad)
