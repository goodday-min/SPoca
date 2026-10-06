"""단어장(words) 요청·응답 모양과 검사 규칙.

복습 단계(stage)와 상태(status)는 사용자가 직접 바꾸지 않는다.
요청 모양(WordCreate)에는 이 값들이 없고, 서버가 저장할 때 정한다.
"""
from datetime import date as _date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

WORD_MAX_LENGTH = 50
MEANING_MAX_LENGTH = 200
EXAMPLE_MAX_LENGTH = 300

# 복습 단계 순서와, 등록일로부터 며칠 뒤에 묻는지 (PRD F5)
STAGES = ("New", "V1", "V2", "V3", "Master")
STAGE_OFFSET_DAYS = {"New": 0, "V1": 1, "V2": 3, "V3": 7, "Master": 30}

Stage = Literal["New", "V1", "V2", "V3", "Master"]
# 저장 값은 영어 코드, 화면에서 한글(복습 중 / 외움 / 못 외움)로 바꿔 보여준다.
Status = Literal["reviewing", "passed", "failed"]
Source = Literal["scan", "manual", "english_chat"]


def _check_date_exists(v: str | None) -> str | None:
    """형식이 맞아도 2026-13-45 같은 없는 날짜는 거부한다."""
    if v is None:
        return v
    try:
        _date.fromisoformat(v)
    except ValueError:
        raise ValueError("존재하지 않는 날짜예요. YYYY-MM-DD 형식으로 입력해 주세요.")
    return v


class WordBase(BaseModel):
    word: str = Field(
        ...,
        min_length=1,
        max_length=WORD_MAX_LENGTH,
        description=f"단어 (최대 {WORD_MAX_LENGTH}자)",
        examples=["resilient"],
    )
    meaning: str = Field(
        "",
        max_length=MEANING_MAX_LENGTH,
        description=f"뜻 (비워 둘 수 있음, 최대 {MEANING_MAX_LENGTH}자)",
        examples=["회복력 있는"],
    )
    example: str = Field(
        "",
        max_length=EXAMPLE_MAX_LENGTH,
        description=f"예문 (선택, 최대 {EXAMPLE_MAX_LENGTH}자)",
        examples=["She is resilient."],
    )

    @field_validator("word", "meaning", "example", mode="before")
    @classmethod
    def strip_spaces(cls, v):
        # 앞뒤 공백은 지운다. 공백만 입력한 단어는 비어 있는 것으로 보고 거부한다.
        return v.strip() if isinstance(v, str) else v


class WordCreate(WordBase):
    """POST /api/words 요청 본문. 단계·상태는 받지 않는다(서버가 New / 복습 중으로 시작)."""

    registered_date: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="등록일 (YYYY-MM-DD, 복습 기준일). 비우면 오늘",
        examples=["2026-10-06"],
    )

    @field_validator("registered_date")
    @classmethod
    def date_must_exist(cls, v: str | None) -> str | None:
        return _check_date_exists(v)


class WordUpdate(WordBase):
    """PUT /api/words/{id} 요청 본문. 단어·뜻·예문만 받는다.
    단계·상태·등록일을 같이 보내도 무시한다(복습 결과로만 바뀐다)."""


class WordOut(WordBase):
    """응답: 저장된 단어 (문서 ID, 단계·상태 포함)"""

    id: str = Field(..., description="Firestore 문서 ID")
    registered_date: str = Field(..., description="등록일 (복습 기준일)")
    stage: Stage = Field(..., description="지금 묻는 복습 단계")
    status: Status = Field(..., description="reviewing(복습 중) / passed(외움) / failed(못 외움)")
    source: Source = Field(..., description="등록 경로: scan / manual / english_chat")
    passed_stage: Stage | None = Field(None, description="패스(외움)한 단계. 아직 없으면 null")
    reviewed_at: str | None = Field(None, description="마지막 복습일. 아직 없으면 null")


class WordListOut(BaseModel):
    """GET /api/words 응답: 모든 단어 (정렬 기준에 따른 순서)"""

    items: list[WordOut]


# 사진은 화면에서 줄여서(긴 변 1600px 이하 JPEG) 보내므로 보통 1MB 안팎이다. 넉넉히 약 5MB(글자로는 7,000,000자)까지.
IMAGE_MAX_LENGTH = 7_000_000
SCAN_MAX_WORDS = 50


class WordScanRequest(BaseModel):
    """POST /api/words/scan 요청 본문: 책 사진 한 장 + (선택) 등록일"""

    image: str = Field(
        ...,
        max_length=IMAGE_MAX_LENGTH,
        pattern=r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$",
        description="사진을 base64 글자로 바꾼 data URL (예: data:image/jpeg;base64,/9j/4AAQ...)",
    )
    registered_date: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="등록일 (YYYY-MM-DD). 비우면 오늘, 오늘보다 이전 날짜는 거부. 인식된 모든 단어에 같은 등록일",
        examples=["2026-10-06"],
    )

    @field_validator("registered_date")
    @classmethod
    def date_must_exist(cls, v: str | None) -> str | None:
        return _check_date_exists(v)


class WordScanOut(BaseModel):
    """스캔 결과: 등록된 단어 목록"""

    count: int = Field(..., description="등록된 단어 수")
    items: list[WordOut]
