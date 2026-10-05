"""코칭 채팅 대화 기록 저장·조회 로직. Firestore 컬렉션 이름: conversations"""
from datetime import datetime, timezone

from app.schemas.conversation import ConversationCreate

COLLECTION = "conversations"
AUTO_TITLE_LENGTH = 30


class ConversationNotFoundError(Exception):
    """해당 ID의 대화가 없을 때"""


def _col():
    from app.core.firebase import get_db  # 지연 import: 테스트에서 firebase 없이도 make_title 사용 가능

    return get_db().collection(COLLECTION)


def make_title(title: str | None, messages: list) -> str:
    """제목이 비어 있으면 첫 질문(user 메시지)의 앞부분으로 만든다."""
    if title and title.strip():
        return title.strip()
    first_user = next((m.content for m in messages if m.role == "user"), messages[0].content)
    text = " ".join(first_user.split())  # 줄바꿈·연속 공백 정리
    if len(text) > AUTO_TITLE_LENGTH:
        return text[:AUTO_TITLE_LENGTH] + "…"
    return text


def _summary(doc) -> dict:
    d = doc.to_dict()
    return {
        "id": doc.id,
        "title": d["title"],
        "created_at": d["created_at"],
        "updated_at": d["updated_at"],
        "message_count": len(d.get("messages", [])),
    }


def _detail(doc) -> dict:
    return {**_summary(doc), "messages": doc.to_dict()["messages"]}


def create(payload: ConversationCreate) -> dict:
    now = datetime.now(timezone.utc)
    data = {
        "title": make_title(payload.title, payload.messages),
        "messages": [m.model_dump() for m in payload.messages],
        "created_at": now,
        "updated_at": now,
    }
    _, ref = _col().add(data)
    return _detail(ref.get())


def append(conversation_id: str, new_messages: list[dict]) -> dict:
    """기존 대화 뒤에 메시지를 이어 붙이고 updated_at을 갱신한다."""
    ref = _col().document(conversation_id)
    doc = ref.get()
    if not doc.exists:
        raise ConversationNotFoundError(conversation_id)
    messages = doc.to_dict()["messages"] + new_messages
    ref.update({"messages": messages, "updated_at": datetime.now(timezone.utc)})
    return _detail(ref.get())


def list_items(limit: int) -> list[dict]:
    """최근에 이어간 대화부터 limit개. 메시지 본문은 담지 않는다."""
    from google.cloud.firestore_v1 import Query

    query = _col().order_by("updated_at", direction=Query.DESCENDING).limit(limit)
    return [_summary(d) for d in query.stream()]


def get(conversation_id: str) -> dict:
    doc = _col().document(conversation_id).get()
    if not doc.exists:
        raise ConversationNotFoundError(conversation_id)
    return _detail(doc)


def delete(conversation_id: str) -> None:
    ref = _col().document(conversation_id)
    if not ref.get().exists:
        raise ConversationNotFoundError(conversation_id)
    ref.delete()
