"""코칭 채팅 대화 기록(conversations) 요청·응답 모양."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TITLE_MAX_LENGTH = 100
MESSAGE_MAX_LENGTH = 4000


class Message(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="말한 사람: 나(user) 또는 AI(assistant)")
    content: str = Field(..., min_length=1, max_length=MESSAGE_MAX_LENGTH, description="메시지 내용")
    tools: list[str] = Field(
        default_factory=list, max_length=20, description="이 답변을 만들려고 AI가 조회한 것 (AI 메시지에만, 예: '기간별 학습 기록(9/15)')"
    )


class ConversationCreate(BaseModel):
    """POST /api/conversations 요청 본문"""

    title: str | None = Field(
        None,
        max_length=TITLE_MAX_LENGTH,
        description="대화 제목. 비우면 첫 질문의 앞부분으로 만든다",
        examples=["최근 7일 어땠어?"],
    )
    messages: list[Message] = Field(..., min_length=1, description="대화 메시지 목록 (오래된 순)")


class ConversationSummaryOut(BaseModel):
    """목록 응답: 메시지는 빼고 제목과 시각만 (불러올 때 상세 조회로 전체를 받는다)"""

    id: str = Field(..., description="Firestore 문서 ID")
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(0, description="대화에 담긴 메시지 수")


class ConversationOut(ConversationSummaryOut):
    """상세 응답: 메시지 전체 포함"""

    messages: list[Message]
