from fastapi import APIRouter, HTTPException, Query, Response, status

from app.schemas.conversation import ConversationCreate, ConversationOut, ConversationSummaryOut
from app.services import conversation_service
from app.services.conversation_service import ConversationNotFoundError

router = APIRouter(prefix="/conversations", tags=["conversations"])

NOT_FOUND_MESSAGE = "해당 대화를 찾을 수 없어요"


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate):
    """대화 저장"""
    return conversation_service.create(payload)


@router.get("", response_model=list[ConversationSummaryOut])
def list_conversations(limit: int = Query(50, ge=1, le=100, description="불러올 개수")):
    """대화 목록 (최근에 이어간 순). 메시지는 포함하지 않고, 불러올 때 GET /{id} 로 받는다."""
    return conversation_service.list_items(limit)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str):
    """특정 대화의 메시지 전체"""
    try:
        return conversation_service.get(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str):
    """대화 삭제"""
    try:
        conversation_service.delete(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
