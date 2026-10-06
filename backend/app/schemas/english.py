"""책 사진 영어 대화(english) 요청·응답 모양.

서버는 대화를 저장하지 않는다(단어 추출에만 쓴다). 그래서 책 내용(book_text)과 지금까지의 대화(messages)는
화면이 들고 있다가 요청 때마다 같이 보낸다.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.word import IMAGE_MAX_LENGTH, WordOut

MAX_PAGES = 3  # 책 사진은 최대 3장
BOOK_TEXT_MAX_LENGTH = 8000
TURN_MAX_LENGTH = 1000
MAX_TURNS = 80  # 대화 기록(말풍선) 최대 개수
FINISH_MAX_WORDS = 10  # 대화 종료 때 단어장에 자동 등록하는 최대 단어 수

Level = Literal["Beginner", "Advanced"]

IMAGE_PATTERN = r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$"


class EnglishScanRequest(BaseModel):
    """POST /api/english/scan: 책 사진 1~3장을 합쳐서 읽는다"""

    images: list[str] = Field(
        ...,
        min_length=1,
        max_length=MAX_PAGES,
        description="사진을 base64 글자로 바꾼 data URL 목록 (1~3장)",
    )

    @field_validator("images")
    @classmethod
    def check_each_image(cls, v: list[str]) -> list[str]:
        import re

        for img in v:
            if len(img) > IMAGE_MAX_LENGTH or not re.match(IMAGE_PATTERN, img):
                raise ValueError("사진은 JPEG·PNG·WebP 형식이고 너무 크지 않아야 해요.")
        return v


class EnglishScanOut(BaseModel):
    text: str = Field(..., description="인식한 책 내용 (대화·종료 요청에 그대로 다시 보낸다)")
    sentence_count: int = Field(..., description="인식한 문장 수")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=TURN_MAX_LENGTH)

    @field_validator("content")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v


class EnglishChatRequest(BaseModel):
    """POST /api/english/chat: 대화 한 턴. messages가 비어 있으면 AI가 먼저 말을 건다"""

    book_text: str = Field(..., min_length=1, max_length=BOOK_TEXT_MAX_LENGTH)
    level: Level
    messages: list[Turn] = Field(default_factory=list, max_length=MAX_TURNS, description="지금까지의 대화(오래된 순)")

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, v: list[Turn]) -> list[Turn]:
        if v and v[-1].role != "user":
            raise ValueError("마지막 메시지는 사용자가 한 말이어야 해요.")
        return v


class EnglishChatOut(BaseModel):
    reply: str = Field(..., description="AI의 영어 답변")
    finished: bool = Field(False, description="AI가 대화를 마무리했으면 true (화면이 종료 흐름으로 넘어간다)")


class EnglishFinishRequest(BaseModel):
    """POST /api/english/finish: 대화 종료 → 핵심 단어를 뽑아 단어장에 등록"""

    book_text: str = Field(..., min_length=1, max_length=BOOK_TEXT_MAX_LENGTH)
    messages: list[Turn] = Field(default_factory=list, max_length=MAX_TURNS)


class EnglishFinishOut(BaseModel):
    count: int = Field(..., description="등록된 단어 수 (대화를 하지 않았으면 0)")
    items: list[WordOut]
