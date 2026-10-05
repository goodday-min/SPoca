"""학습 기록(data) 저장·조회 로직. Firestore 컬렉션 이름: data

라우터는 요청을 받고 결과를 돌려주기만 하고,
실제 규칙(날짜 중복 검사 등)은 이 파일에서 처리한다.
"""
from google.cloud.firestore_v1 import Query
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.firebase import get_db
from app.schemas.data import DataCreate, DataUpdate

COLLECTION = "data"


class DuplicateDateError(Exception):
    """이미 그 날짜의 기록이 있을 때"""


class DataNotFoundError(Exception):
    """해당 ID의 기록이 없을 때"""


def _col():
    return get_db().collection(COLLECTION)


def _to_item(doc) -> dict:
    d = doc.to_dict()
    return {"id": doc.id, "date": d["date"], "value": d["value"], "memo": d.get("memo", "")}


def _find_by_date(date: str):
    docs = list(_col().where(filter=FieldFilter("date", "==", date)).limit(1).stream())
    return docs[0] if docs else None


def create(payload: DataCreate) -> dict:
    if _find_by_date(payload.date) is not None:
        raise DuplicateDateError(payload.date)
    # 문서 ID는 Firestore가 자동으로 만든다.
    _, ref = _col().add(payload.model_dump())
    return _to_item(ref.get())


def list_items(limit: int, cursor: str | None, start: str | None = None, end: str | None = None) -> dict:
    """최신 날짜순으로 limit개를 돌려준다.
    cursor 가 있으면 그 날짜보다 이전 기록부터, start/end 가 있으면 그 기간(양 끝 포함)만."""
    query = _col().order_by("date", direction=Query.DESCENDING)
    if start:
        query = query.where(filter=FieldFilter("date", ">=", start))
    if end:
        query = query.where(filter=FieldFilter("date", "<=", end))
    if cursor:
        query = query.where(filter=FieldFilter("date", "<", cursor))
    # 다음 페이지가 있는지 알기 위해 1개를 더 읽는다.
    docs = list(query.limit(limit + 1).stream())
    items = [_to_item(d) for d in docs[:limit]]
    next_cursor = items[-1]["date"] if len(docs) > limit else None
    return {"items": items, "next_cursor": next_cursor}


def update(doc_id: str, payload: DataUpdate) -> dict:
    ref = _col().document(doc_id)
    if not ref.get().exists:
        raise DataNotFoundError(doc_id)
    # 날짜를 바꾸는 수정도 다른 기록과 겹치면 안 된다. (자기 자신은 제외)
    other = _find_by_date(payload.date)
    if other is not None and other.id != doc_id:
        raise DuplicateDateError(payload.date)
    ref.set(payload.model_dump())
    return _to_item(ref.get())


def delete(doc_id: str) -> None:
    ref = _col().document(doc_id)
    if not ref.get().exists:
        raise DataNotFoundError(doc_id)
    ref.delete()
