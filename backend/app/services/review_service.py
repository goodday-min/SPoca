"""복습 로직: 오늘 복습할 단어 고르기(T3-5)와 복습 완료 처리(T3-6).

규칙(PRD F5):
- 복습 중(reviewing)인 단어만 대상이다. 외움·못 외움으로 끝난 단어는 다시 묻지 않는다.
- 단어마다 '지금 묻는 단계'(stage)가 하나뿐이고, 그 단계의 복습일 = 등록일 + 0/1/3/7/30일(등록일 기준 누적).
- 복습일이 오늘이거나 이미 지났으면 대상이다. 등록일이 미래라 복습일도 미래면 그날까지 나오지 않는다.
- 복습일을 놓쳐도 지금 단계로 한 번만 묻는다. 여러 단계를 건너뛰어 쌓아 두지 않는다.
  (단어에 단계가 하나만 저장되므로 자연히 '놓친 가장 낮은 단계'가 된다.)
- 탭하지 않은 단어 = 패스(외움, 끝). 탭한 단어 = 못 외움 → 다음 단계(다음 복습일은 등록일 기준 그대로).
  Master에서 탭하면 더 올라갈 단계가 없어 '못 외움'으로 끝난다.
- 복습은 하루 한 번. 끝나면 오늘 패스한 수가 학습 기록(data)의 value로 자동 기록된다(메모는 그대로).

연속 학습 일수(T3-7):
- 첫 복습을 마친 날부터 센다(그 전에는 0). 복습을 끝낸 날은 +1.
- 복습 대상이 없는 날은 끊기지 않고 그날 +1. 대상이 있는데 복습하지 않은 날은 끊긴다(0으로 돌아감).
- 복습을 끝낸 날의 값(그날까지의 연속 일수)을 reviews 문서의 streak 에 저장한다.
- 복습하지 않고 지난 날들은 단어 상태만으로 계산한다. 복습한 날에만 단어가 바뀌므로, 마지막 복습 이후
  '대상이 처음 생기는 날'을 알면 그 전날들은 모두 대상 없는 날, 그날부터는 끊긴 날이다.
"""
from datetime import date, datetime, timedelta, timezone

from app.schemas.word import STAGE_OFFSET_DAYS, STAGES
from app.services import word_service

REVIEWS = "reviews"  # 날짜(YYYY-MM-DD)가 문서 ID. 하루에 문서 1개 = '오늘 복습 완료' 표시
DATA = "data"


class AlreadyReviewedError(Exception):
    """오늘 복습을 이미 마쳤을 때 (하루 한 번)"""


class NothingToReviewError(Exception):
    """오늘 복습할 단어가 하나도 없을 때"""


class InvalidTappedWordsError(Exception):
    """탭한 단어 중에 오늘 복습 대상이 아닌 ID가 있을 때"""


# ---------------------------------------------------------------- 계산 (Firestore 없이 테스트 가능)
def due_date(registered_date: str, stage: str) -> date:
    """이 단계의 복습일. 예: 10/5 등록, V2 → 10/8"""
    return date.fromisoformat(registered_date) + timedelta(days=STAGE_OFFSET_DAYS[stage])


def select_due(items: list[dict], today: date) -> list[dict]:
    """words 목록에서 오늘 복습할 단어만 골라 등록일이 빠른 순으로 돌려준다(같으면 먼저 만든 순)."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    due = [
        w
        for w in items
        if w["status"] == "reviewing" and due_date(w["registered_date"], w["stage"]) <= today
    ]
    due.sort(key=lambda w: (w["registered_date"], w.get("created_at") or epoch))
    return [
        {
            "id": w["id"],
            "word": w["word"],
            "meaning": w["meaning"],
            "example": w["example"],
            "registered_date": w["registered_date"],
            "stage": w["stage"],
            "due_date": due_date(w["registered_date"], w["stage"]).isoformat(),
        }
        for w in due
    ]


def plan_transitions(due: list[dict], tapped_ids: set[str], today: date) -> list[dict]:
    """복습 결과로 각 단어에 어떤 변경을 저장할지 계산한다.

    돌려주는 항목: {id, tapped, changes} — changes 는 words 문서에 덮어쓸 필드.
    - 탭 안 함: status=passed, passed_stage=지금 단계, reviewed_at=오늘 (단계는 그대로)
    - 탭함 + Master 아님: stage=다음 단계 (status는 reviewing 그대로)
    - 탭함 + Master: status=failed (단계는 Master 그대로)
    """
    plan = []
    for w in due:
        tapped = w["id"] in tapped_ids
        changes = {"reviewed_at": today.isoformat()}
        if not tapped:
            changes.update(status="passed", passed_stage=w["stage"])
        elif w["stage"] == STAGES[-1]:
            changes.update(status="failed")
        else:
            changes.update(stage=STAGES[STAGES.index(w["stage"]) + 1])
        plan.append({"id": w["id"], "tapped": tapped, "changes": changes})
    return plan


def first_target_day(words: list[dict], last_review: date) -> date | None:
    """마지막 복습일 다음 날부터 따졌을 때, 복습 대상이 처음 생기는 날. 복습 중인 단어가 없으면 None.

    단어의 복습일이 이미 지났어도(복습일 <= 마지막 복습일) 그 단어는 마지막 복습 바로 다음 날부터 대상이다.
    """
    dues = [due_date(w["registered_date"], w["stage"]) for w in words if w["status"] == "reviewing"]
    if not dues:
        return None
    return max(min(dues), last_review + timedelta(days=1))


def streak_through_yesterday(last_review: date | None, last_streak: int, words: list[dict], today: date) -> int:
    """어제까지의 연속 일수 (오늘은 아직 세지 않은 값).

    - 복습한 적이 없으면 0.
    - 마지막 복습이 어제이거나 오늘이면 그 값 그대로.
    - 그 사이에 대상이 생긴 날이 있으면(어제까지) 끊겼으니 0. 없었으면 대상 없는 날마다 +1.
    """
    if last_review is None:
        return 0
    yesterday = today - timedelta(days=1)
    if last_review >= yesterday:
        return last_streak
    target_day = first_target_day(words, last_review)
    if target_day is not None and target_day <= yesterday:
        return 0
    return last_streak + (yesterday - last_review).days


def streak_now(last_review: date | None, last_streak: int, words: list[dict], today: date) -> dict:
    """지금 홈에 보여 줄 연속 일수. 오늘 복습을 마쳤거나 오늘 복습 대상이 없으면 오늘까지 세고,
    복습 대상이 있는데 아직 안 했으면 어제까지의 숫자를 보여 준다."""
    if last_review == today:
        return {"streak": last_streak, "completed_today": True, "counts_today": True}
    base = streak_through_yesterday(last_review, last_streak, words, today)
    if last_review is None:  # 아직 한 번도 복습하지 않았으면 대상이 없어도 세지 않는다
        return {"streak": 0, "completed_today": False, "counts_today": False}
    target_day = first_target_day(words, last_review)
    no_target_today = target_day is None or target_day > today
    return {"streak": base + 1 if no_target_today else base, "completed_today": False, "counts_today": no_target_today}


# ---------------------------------------------------------------- Firestore
def _db():
    from app.core.firebase import get_db  # 지연 import: 계산 함수는 firebase 없이도 테스트할 수 있게

    return get_db()


def _find_data_doc(db, day: str):
    from google.cloud.firestore_v1.base_query import FieldFilter

    docs = list(db.collection(DATA).where(filter=FieldFilter("date", "==", day)).limit(1).stream())
    return docs[0] if docs else None


def _latest_review(db) -> dict | None:
    """가장 최근 복습 기록(날짜가 가장 늦은 reviews 문서). 없으면 None."""
    from google.cloud.firestore_v1 import Query

    docs = list(db.collection(REVIEWS).order_by("date", direction=Query.DESCENDING).limit(1).stream())
    return docs[0].to_dict() if docs else None


def _last_review_info(db) -> tuple[date | None, int]:
    last = _latest_review(db)
    if last is None:
        return None, 0
    return date.fromisoformat(last["date"]), last.get("streak", 0)


def get_streak(today: date | None = None) -> dict:
    """GET /api/streak: 홈 배지에 보여 줄 연속 일수"""
    today = today or word_service.today_kst()
    db = _db()
    last_review, last_streak = _last_review_info(db)
    out = streak_now(last_review, last_streak, _all_words(db), today)
    return {"date": today.isoformat(), **out}


def _all_words(db) -> list[dict]:
    return [word_service.to_item(d) for d in db.collection(word_service.COLLECTION).stream()]


def _review_doc(db, day: str):
    return db.collection(REVIEWS).document(day)


def today_review(today: date | None = None) -> dict:
    """GET /api/review/today: 오늘 복습 대상. 오늘 복습을 이미 마쳤으면 대상 목록은 비운다."""
    today = today or word_service.today_kst()
    db = _db()
    done = _review_doc(db, today.isoformat()).get()
    if done.exists:
        return {
            "date": today.isoformat(),
            "count": 0,
            "completed_today": True,
            "passed_count": done.to_dict().get("passed_count", 0),
            "items": [],
        }
    due = select_due(_all_words(db), today)
    return {"date": today.isoformat(), "count": len(due), "completed_today": False, "passed_count": 0, "items": due}


def complete(tapped_ids: list[str], today: date | None = None) -> dict:
    """POST /api/review/complete: 복습 결과를 저장한다. 한 번에 모두 저장하고, 중간에 실패하면 아무것도 저장하지 않는다."""
    today = today or word_service.today_kst()
    day = today.isoformat()
    db = _db()

    review_ref = _review_doc(db, day)
    if review_ref.get().exists:
        raise AlreadyReviewedError(day)
    words = _all_words(db)
    due = select_due(words, today)
    if not due:
        raise NothingToReviewError(day)
    tapped = set(tapped_ids)
    if not tapped <= {w["id"] for w in due}:
        raise InvalidTappedWordsError()

    last_review, last_streak = _last_review_info(db)
    streak = streak_through_yesterday(last_review, last_streak, words, today) + 1  # 오늘 복습을 마쳤으니 +1

    plan = plan_transitions(due, tapped, today)
    passed_count = sum(1 for p in plan if not p["tapped"])

    batch = db.batch()
    words_col = db.collection(word_service.COLLECTION)
    for p in plan:
        batch.update(words_col.document(p["id"]), p["changes"])
    # 오늘 학습 기록의 값만 바꾸고 메모는 그대로 둔다. 기록이 없으면 새로 만든다(메모는 빈 값).
    data_doc = _find_data_doc(db, day)
    if data_doc is not None:
        batch.update(data_doc.reference, {"value": passed_count})
    else:
        batch.set(db.collection(DATA).document(), {"date": day, "value": passed_count, "memo": ""})
    # create 는 이미 있으면 실패한다 → 동시에 두 번 눌러도 하루 한 번만 저장된다.
    batch.create(
        review_ref,
        {
            "date": day,
            "reviewed_count": len(due),
            "passed_count": passed_count,
            "retry_ids": [p["id"] for p in plan if p["tapped"]],
            "streak": streak,
            "completed_at": datetime.now(timezone.utc),
        },
    )
    batch.commit()

    by_id = {w["id"]: w for w in due}
    retry = [
        {
            "id": p["id"],
            "word": by_id[p["id"]]["word"],
            "meaning": by_id[p["id"]]["meaning"],
            "stage": p["changes"].get("stage", by_id[p["id"]]["stage"]),
            "status": p["changes"].get("status", "reviewing"),
        }
        for p in plan
        if p["tapped"]
    ]
    return {
        "date": day,
        "reviewed_count": len(due),
        "passed_count": passed_count,
        "retry_count": len(retry),
        "retry_items": retry,
        "streak": streak,
    }
