"""단어장(words) 저장·조회 로직. Firestore 컬렉션 이름: words

라우터는 요청을 받고 결과를 돌려주기만 하고, 실제 규칙은 이 파일에서 처리한다.
(T3-1 저장 구조·새 단어 만들기, T3-2 등록, T3-3 목록·수정·삭제)
"""
from datetime import date, datetime, timedelta, timezone

from app.schemas.word import STAGES, WordCreate, WordUpdate

COLLECTION = "words"


class WordNotFoundError(Exception):
    """해당 ID의 단어가 없을 때"""


class PastRegisteredDateError(Exception):
    """등록일이 오늘보다 이전일 때 (오늘이나 미래만 고를 수 있다)"""


KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    return datetime.now(KST).date()


def check_registered_date(registered_date: str | None, today: date) -> None:
    """등록일을 지정했다면 오늘이거나 미래여야 한다. 비어 있으면(=오늘) 통과."""
    if registered_date is not None and date.fromisoformat(registered_date) < today:
        raise PastRegisteredDateError(registered_date)


def _col():
    from app.core.firebase import get_db  # 지연 import: 테스트에서 firebase 없이도 new_word_doc 사용 가능

    return get_db().collection(COLLECTION)


def new_word_doc(payload: WordCreate, source: str, today: date, now: datetime | None = None) -> dict:
    """Firestore에 저장할 새 단어 문서를 만든다.

    새 단어는 항상 New 단계, 복습 중 상태로 시작한다.
    등록일을 안 보냈으면 오늘, passed_stage·reviewed_at 은 복습 전이라 비어 있다.
    created_at 은 화면에 보이지 않는 내부용(같은 등록일끼리 정렬할 때만 쓴다).
    """
    return {
        "word": payload.word,
        "meaning": payload.meaning,
        "example": payload.example,
        "registered_date": payload.registered_date or today.isoformat(),
        "stage": "New",
        "status": "reviewing",
        "source": source,
        "passed_stage": None,
        "reviewed_at": None,
        "created_at": now or datetime.now(timezone.utc),
    }


def to_item(doc) -> dict:
    d = doc.to_dict()
    return {
        "id": doc.id,
        "word": d["word"],
        "meaning": d.get("meaning", ""),
        "example": d.get("example", ""),
        "registered_date": d["registered_date"],
        "stage": d["stage"],
        "status": d["status"],
        "source": d["source"],
        "passed_stage": d.get("passed_stage"),
        "reviewed_at": d.get("reviewed_at"),
        "created_at": d.get("created_at"),  # 정렬용. 응답 모양(WordOut)에는 없어서 밖으로 나가지 않는다
    }


def sort_items(items: list[dict], sort: str) -> list[dict]:
    """목록 정렬.

    latest: 등록일이 나중인 단어 먼저, 같은 등록일이면 더 늦게 만든 단어 먼저.
    stage : New → V1 → V2 → V3 → Master 순. 복습이 끝난 단어(외움·못 외움)는 맨 아래.
            같은 단계 안에서는 latest 와 같은 순서.
    created_at 이 없는 옛 문서는 가장 먼저 만든 것으로 본다.
    """
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    # 안정 정렬을 두 번 써서 '큰 값 먼저'를 간단하게 만든다: 먼저 보조 기준, 나중에 주 기준.
    by_latest = sorted(items, key=lambda w: w.get("created_at") or epoch, reverse=True)
    by_latest = sorted(by_latest, key=lambda w: w["registered_date"], reverse=True)
    if sort == "latest":
        return by_latest
    return sorted(by_latest, key=lambda w: (w["status"] != "reviewing", STAGES.index(w["stage"])))


def create(payload: WordCreate, source: str, today: date | None = None) -> dict:
    today = today or today_kst()
    check_registered_date(payload.registered_date, today)
    # 같은 단어도 중복 등록할 수 있다. (등록일이 다르면 복습 일정이 따로 필요하므로)
    _, ref = _col().add(new_word_doc(payload, source, today))
    return to_item(ref.get())


def list_items(sort: str = "latest") -> dict:
    """모든 단어를 한 번에 돌려준다. (개인 단어장이라 나눠 불러오지 않는다)"""
    items = [to_item(d) for d in _col().stream()]
    return {"items": sort_items(items, sort)}


def update(doc_id: str, payload: WordUpdate) -> dict:
    """단어·뜻·예문만 바꾼다. 단계·상태·등록일 등은 이 함수로 바뀌지 않는다."""
    ref = _col().document(doc_id)
    if not ref.get().exists:
        raise WordNotFoundError(doc_id)
    ref.update({"word": payload.word, "meaning": payload.meaning, "example": payload.example})
    return to_item(ref.get())


def delete(doc_id: str) -> None:
    ref = _col().document(doc_id)
    if not ref.get().exists:
        raise WordNotFoundError(doc_id)
    ref.delete()


def create_many(entries: list[dict], registered_date: str | None, source: str, today: date | None = None) -> list[dict]:
    """여러 단어를 한 번에 등록한다(스캔용). 모두 같은 등록일, New 단계·복습 중으로 시작."""
    today = today or today_kst()
    check_registered_date(registered_date, today)
    from app.core.firebase import get_db

    db = get_db()
    db_col = db.collection(COLLECTION)
    batch = db.batch()  # 한 번에 저장(중간에 실패하면 전부 저장되지 않는다)
    items = []
    for e in entries:
        payload = WordCreate(word=e["word"], meaning=e.get("meaning", ""), example=e.get("example", ""), registered_date=registered_date)
        doc = new_word_doc(payload, source, today)
        ref = db_col.document()  # 문서 ID는 Firestore가 자동으로 만든다
        batch.set(ref, doc)
        items.append({"id": ref.id, **doc})
    batch.commit()
    return items
