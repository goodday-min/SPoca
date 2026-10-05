"""코칭 채팅(POST /api/chat) 요청·응답 모양."""
from pydantic import BaseModel, Field, field_validator

from app.schemas.conversation import MESSAGE_MAX_LENGTH


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(
        None, description="이어갈 대화 ID. 비우면 새 대화를 만든다"
    )
    message: str = Field(
        ..., max_length=MESSAGE_MAX_LENGTH, description="사용자 질문", examples=["최근 7일 어땠어?"]
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("질문을 입력해 주세요")
        return v


class ChatResponse(BaseModel):
    conversation_id: str = Field(..., description="저장된 대화 ID (다음 질문에 그대로 보내면 이어진다)")
    title: str
    reply: str = Field(..., description="AI 답변")
