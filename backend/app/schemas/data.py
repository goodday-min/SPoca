"""학습 기록(data) 요청·응답 모양과 검사 규칙.

Pydantic이 요청이 들어오자마자 아래 규칙으로 검사하고,
어기면 FastAPI가 422 오류를 자동으로 돌려준다.
"""
from datetime import date as _date

from pydantic import BaseModel, Field, field_validator

MEMO_MAX_LENGTH = 200


class DataBase(BaseModel):
    date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="날짜 (YYYY-MM-DD). 날짜당 기록은 1개",
        examples=["2026-10-05"],
    )
    value: int = Field(
        ...,
        strict=True,
        ge=0,
        description="그날 외운(패스한) 단어 수. 0 이상의 정수",
        examples=[12],
    )
    memo: str = Field(
        "",
        max_length=MEMO_MAX_LENGTH,
        description=f"자유 메모 (최대 {MEMO_MAX_LENGTH}자)",
        examples=["복습 꾸준히"],
    )

    @field_validator("date")
    @classmethod
    def date_must_exist(cls, v: str) -> str:
        # 형식이 맞아도 2026-13-45 같은 없는 날짜는 거부한다.
        try:
            _date.fromisoformat(v)
        except ValueError:
            raise ValueError("존재하지 않는 날짜예요. YYYY-MM-DD 형식으로 입력해 주세요.")
        return v


class DataCreate(DataBase):
    """POST /api/data 요청 본문"""


class DataUpdate(DataBase):
    """PUT /api/data/{id} 요청 본문 (모든 항목을 다시 보낸다)"""


class DataOut(DataBase):
    """응답: 저장된 기록 (문서 ID 포함)"""

    id: str = Field(..., description="Firestore 문서 ID")


class DataListOut(BaseModel):
    """GET /api/data 응답: 최신 날짜순 목록과 '더 보기'용 커서"""

    items: list[DataOut]
    next_cursor: str | None = Field(
        None,
        description="더 불러올 기록이 있으면 마지막 항목의 날짜. 다음 요청의 cursor 값으로 보낸다",
    )
