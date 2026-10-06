"""학습 통계 계산: 최장 연속 기록, 요일별 평균. build_statistics 는 Firestore 없이 계산만 한다."""
from datetime import date, timedelta

from app.services import data_service

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday(): 월=0 … 일=6


def _longest_streak(dates: list[date]) -> dict:
    """날짜가 하루씩 이어진 가장 긴 구간. 길이가 같으면 더 최근 구간을 돌려준다."""
    best = {"days": 0, "start": None, "end": None}
    run_start = prev = None
    for d in sorted(set(dates)):
        if prev is not None and d - prev == timedelta(days=1):
            pass
        else:
            run_start = d
        prev = d
        length = (d - run_start).days + 1
        if length >= best["days"]:
            best = {"days": length, "start": run_start.isoformat(), "end": d.isoformat()}
    return best


def build_statistics(records: list[dict], start: str | None = None, end: str | None = None) -> dict:
    sums = [0] * 7
    counts = [0] * 7
    dates = []
    for r in records:
        d = date.fromisoformat(r["date"])
        dates.append(d)
        sums[d.weekday()] += r["value"]
        counts[d.weekday()] += 1
    weekday_average = [
        {"weekday": WEEKDAYS[i], "average": round(sums[i] / counts[i], 1) if counts[i] else None, "count": counts[i]}
        for i in range(7)
    ]
    # 평균은 반올림 전의 값으로 비교한다 (먼저 오는 요일이 우선)
    best = None
    for i in range(7):
        if counts[i] and (best is None or sums[i] / counts[i] > sums[best] / counts[best]):
            best = i
    return {
        "period": {"start": start, "end": end},
        "longest_streak": _longest_streak(dates),
        "weekday_average": weekday_average,
        "best_weekday": WEEKDAYS[best] if best is not None else None,
    }


def get_statistics(start: str | None = None, end: str | None = None) -> dict:
    return build_statistics(data_service.export_items(start, end), start, end)
