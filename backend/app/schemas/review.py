"""복습(review) 요청·응답 모양.

복습 화면에는 뜻이 비어 있는 단어도 나올 수 있다(뜻은 탭했을 때만 보여 주므로 빈 값이면 비어 보인다).
"""
from pydantic import BaseModel, Field

from app.schemas.word import Stage, Status


class ReviewWordOut(BaseModel):
    """오늘 복습할 단어 한 개"""

    id: str = Field(..., description="Firestore 문서 ID")
    word: str
    meaning: str = Field(..., description="뜻 (비어 있을 수 있음)")
    example: str = Field(..., description="예문 (비어 있을 수 있음)")
    registered_date: str = Field(..., description="등록일 (복습 기준일)")
    stage: Stage = Field(..., description="지금 묻는 복습 단계")
    due_date: str = Field(..., description="이 단계의 복습일 (등록일 + 0/1/3/7/30일). 오늘이거나 이미 지난 날짜")


class ReviewTodayOut(BaseModel):
    """GET /api/review/today 응답: 오늘 복습 대상 + 오늘 복습을 마쳤는지"""

    date: str = Field(..., description="오늘 날짜 (한국 시간 기준 YYYY-MM-DD)")
    count: int = Field(..., description="복습 대상 단어 수. 오늘 복습을 이미 마쳤으면 0")
    completed_today: bool = Field(..., description="오늘 복습을 이미 마쳤는지 (하루 한 번만 할 수 있다)")
    passed_count: int = Field(..., description="오늘 복습에서 외운(패스한) 단어 수. 복습을 마치지 않았으면 0")
    items: list[ReviewWordOut] = Field(..., description="복습 대상 단어 (등록일이 빠른 순, 같으면 먼저 만든 순). 오늘 복습을 마쳤으면 빈 목록")


class ReviewCompleteRequest(BaseModel):
    """POST /api/review/complete 요청 본문: 복습 중 탭한(=헷갈린, 못 외운) 단어의 ID들"""

    tapped_ids: list[str] = Field(
        default_factory=list,
        max_length=500,
        description="탭한 단어의 ID 목록. 여기에 없는 오늘 복습 대상 단어는 모두 패스(외움)로 처리한다. 비워도 된다(전부 패스)",
    )


class RetryWordOut(BaseModel):
    """다시 복습할 단어 (결과 화면의 '다시 복습할 단어' 목록용)"""

    id: str
    word: str
    meaning: str = Field(..., description="뜻 (비어 있을 수 있음)")
    stage: Stage = Field(..., description="복습 후 단어의 단계. Master를 못 외웠으면 Master 그대로")
    status: Status = Field(..., description="reviewing(다음 단계에서 다시 물음) / failed(Master까지 묻고도 못 외워 종료)")


class ReviewCompleteOut(BaseModel):
    """복습 완료 결과"""

    date: str
    reviewed_count: int = Field(..., description="오늘 복습한 단어 수")
    passed_count: int = Field(..., description="외운(패스한) 단어 수 = 학습 기록(data)의 value로 자동 기록")
    retry_count: int = Field(..., description="탭한(다시 복습할) 단어 수")
    retry_items: list[RetryWordOut]
    streak: int = Field(..., description="복습을 마친 오늘까지의 연속 학습 일수 (결과 화면의 'N일 연속!')")


class StreakOut(BaseModel):
    """GET /api/streak 응답: 홈 배지용 연속 학습 일수"""

    date: str = Field(..., description="오늘 날짜 (한국 시간 기준)")
    streak: int = Field(..., description="지금 보여 줄 연속 일수")
    completed_today: bool = Field(..., description="오늘 복습을 마쳤는지")
    counts_today: bool = Field(
        ...,
        description="streak 에 오늘이 들어 있는지. true: 오늘 복습을 마쳤거나 오늘 복습 대상이 없어 오늘까지 센 값 / false: 복습할 단어가 있는데 아직 안 해서 어제까지의 값",
    )
