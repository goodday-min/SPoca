"""리포트 계산: 기간 요약(7일 / 월별 / 전체) + 일별 그래프 데이터 + 단어 단계 분포.

- 7일: 요약 서비스의 '최근 7일(오늘 포함)'과 추세를 그대로 쓴다.
- 월별: 매월 1일~말일. 기록 없는 날은 value=null(빈 칸). 이번 달의 남은 날도 말일까지 빈 칸. 추세는 없다(null).
- 전체: 기록 있는 날만 날짜순. 기간은 첫 기록일~마지막 기록일. 추세는 없다(null).
- 단계 분포는 기간과 상관없이 현재 단어 상태다.
"""
import calendar
from datetime import date

from app.schemas.word import STAGES
from app.services import summary_service
from app.services.summary_service import _stats, build_summary


class InvalidMonthError(ValueError):
    pass


def parse_month(month: str) -> tuple[int, int]:
    try:
        y, m = month.split("-")
        if len(y) != 4 or len(m) != 2:
            raise ValueError
        y, m = int(y), int(m)
        date(y, m, 1)
    except ValueError:
        raise InvalidMonthError("월은 YYYY-MM 형식으로 입력해 주세요.")
    return y, m


def stage_distribution(words: list[dict]) -> dict:
    reviewing = {s: 0 for s in STAGES}
    finished = {"passed": 0, "failed": 0}
    for w in words:
        if w["status"] == "reviewing":
            if w["stage"] in reviewing:
                reviewing[w["stage"]] += 1
        elif w["status"] in finished:
            finished[w["status"]] += 1
    return {"reviewing": reviewing, "finished": finished}


def build_report(records: list[dict], words: list[dict], period: str, month: str | None, today: date) -> dict:
    by_date = {r["date"]: r["value"] for r in records}
    dist = stage_distribution(words)

    if period == "7d":
        recent = build_summary(records, today)["recent_7d"]
        daily = recent["daily"]
        summary = {k: recent[k] for k in ("period", "count", "average", "max", "min", "previous_average", "trend")}
        return {"period": period, "month": None, "summary": summary, "daily": daily, "stage_distribution": dist}

    if period == "month":
        y, m = parse_month(month)
        last = calendar.monthrange(y, m)[1]
        days = [date(y, m, d).isoformat() for d in range(1, last + 1)]
        daily = [{"date": d, "value": by_date.get(d)} for d in days]
        stats = _stats([v["value"] for v in daily if v["value"] is not None])
        stats["period"] = {"start": days[0], "end": days[-1]}
        stats["previous_average"] = None
        stats["trend"] = None
        return {"period": period, "month": f"{y:04d}-{m:02d}", "summary": stats, "daily": daily, "stage_distribution": dist}

    # 전체
    ordered = sorted(by_date)
    daily = [{"date": d, "value": by_date[d]} for d in ordered]
    stats = _stats([by_date[d] for d in ordered])
    stats["period"] = {"start": ordered[0] if ordered else None, "end": ordered[-1] if ordered else None}
    stats["previous_average"] = None
    stats["trend"] = None
    return {"period": "all", "month": None, "summary": stats, "daily": daily, "stage_distribution": dist}


def get_report(period: str, month: str | None) -> dict:
    # Firestore는 실제로 필요할 때만 불러온다. (계산 로직만 따로 시험할 수 있게)
    from app.core.firebase import get_db

    today = summary_service.today_kst()
    if period == "month" and month is None:
        month = today.strftime("%Y-%m")  # 월을 안 보내면 이번 달
    db = get_db()
    records = []
    for d in db.collection("data").select(["date", "value"]).stream():
        x = d.to_dict()
        records.append({"date": x["date"], "value": x["value"]})
    words = []
    for d in db.collection("words").select(["stage", "status"]).stream():
        x = d.to_dict()
        words.append({"stage": x.get("stage"), "status": x.get("status")})
    return build_report(records, words, period, month, today)
