from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service
from app.services.conversation_service import ConversationNotFoundError
from app.services.llm_service import LLMError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest):
    """요약을 시스템 프롬프트에 넣어 GPT에 묻고, 질문·답변을 대화로 자동 저장한다."""
    try:
        return chat_service.chat(payload)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "해당 대화를 찾을 수 없어요")
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
