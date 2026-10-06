"""학습 기록 요약 계산.

- 전체 기간: 첫 기록일 ~ 마지막 기록일, 개수·평균·최대·최소
- 최근 7일: 오늘 포함 7일 (오늘 - 6일 ~ 오늘)
- 이전 7일: 최근 7일 바로 앞 7일 (오늘 - 13일 ~ 오늘 - 7일)
- 평균은 기록이 있는 날만으로 계산한다. (복습하지 않은 날은 0으로 기록하지 않기 때문)
- 최근 7일 날짜별 값(daily)도 함께 준다. 기록 없는 날은 None.
- 추세: 이전 평균 대비 10% 넘게 높으면 증가, 10% 넘게 낮으면 감소, 그 사이는 유지.
  이전 7일에 기록이 없거나 이전 평균이 0이면, 최근 7일에 기록이 없어도 '비교 불가'.
"""
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

# 한국 시간(UTC+9). Render 서버는 UTC로 돌기 때문에 기준을 직접 정한다.
KST = timezone(timedelta(hours=9))
RECENT_DAYS = 7
TREND_THRESHOLD = Fraction(1, 10)  # 10%


def today_kst() -> date:
    return datetime.now(KST).date()


def _stats(values: list[int]) -> dict:
    if not values:
        return {"count": 0, "average": None, "max": None, "min": None}
    return {
        "count": len(values),
        "average": round(sum(values) / len(values), 1),
        "max": max(values),
        "min": min(values),
    }


def _in_range(records: list[dict], start: date, end: date) -> list[int]:
    s, e = start.isoformat(), end.isoformat()
    return [r["value"] for r in records if s <= r["date"] <= e]


def _trend(recent: list[int], previous: list[int]) -> str:
    if not recent or not previous or sum(previous) == 0:
        return "비교 불가"
    # 분수로 계산해 '정확히 10%'가 소수 오차 때문에 틀리게 판정되지 않게 한다.
    recent_avg = Fraction(sum(recent), len(recent))
    previous_avg = Fraction(sum(previous), len(previous))
    if recent_avg > previous_avg * (1 + TREND_THRESHOLD):
        return "증가"
    if recent_avg < previous_avg * (1 - TREND_THRESHOLD):
        return "감소"
    return "유지"


def build_summary(records: list[dict], today: date) -> dict:
    """records: [{"date": "YYYY-MM-DD", "value": int}, ...]"""
    dates = sorted(r["date"] for r in records)
    overall = _stats([r["value"] for r in records])
    overall["period"] = {
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
    }

    recent_end = today
    recent_start = today - timedelta(days=RECENT_DAYS - 1)
    previous_end = recent_start - timedelta(days=1)
    previous_start = recent_start - timedelta(days=RECENT_DAYS)

    recent_values = _in_range(records, recent_start, recent_end)
    previous_values = _in_range(records, previous_start, previous_end)

    recent = _stats(recent_values)
    recent["period"] = {"start": recent_start.isoformat(), "end": recent_end.isoformat()}
    recent["previous_average"] = _stats(previous_values)["average"]
    recent["trend"] = _trend(recent_values, previous_values)
    # 최근 7일 날짜별 값 (오래된 날 → 오늘). 기록 없는 날은 value None
    by_date = {r["date"]: r["value"] for r in records}
    recent["daily"] = [
        {"date": d.isoformat(), "value": by_date.get(d.isoformat())}
        for d in (recent_start + timedelta(days=i) for i in range(RECENT_DAYS))
    ]

    return {"today": today.isoformat(), "overall": overall, "recent_7d": recent}


def get_summary() -> dict:
    # Firestore 연결은 실제로 필요할 때만 불러온다. (계산 로직만 따로 시험할 수 있게)
    from app.core.firebase import get_db

    docs = get_db().collection("data").select(["date", "value"]).stream()
    records = [{"date": d.to_dict()["date"], "value": d.to_dict()["value"]} for d in docs]
    return build_summary(records, today_kst())
