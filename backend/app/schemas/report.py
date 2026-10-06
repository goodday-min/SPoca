"""리포트(report) 응답 모양. 기간 요약 + 일별 그래프 + 단어 단계 분포."""
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.summary import DailyOut, StatsOut, Trend

Period = Literal["7d", "month", "all"]


class ReportSummaryOut(StatsOut):
    # 추세는 최근 7일 보기에서만 값이 있다. 월별·전체 보기에서는 null.
    previous_average: float | None = Field(None, description="그 이전 7일의 평균 (7일 보기에서만)")
    trend: Trend | None = Field(None, description="추세 (7일 보기에서만, 그 밖에는 null)")


class ReviewingStagesOut(BaseModel):
    New: int = 0
    V1: int = 0
    V2: int = 0
    V3: int = 0
    Master: int = 0


class FinishedOut(BaseModel):
    passed: int = Field(0, description="외운 단어 수")
    failed: int = Field(0, description="Master까지 묻고도 못 외운 단어 수")


class StageDistributionOut(BaseModel):
    reviewing: ReviewingStagesOut
    finished: FinishedOut


class ReportOut(BaseModel):
    period: Period
    month: str | None = Field(None, description="월별 보기일 때 YYYY-MM, 그 밖에는 null")
    summary: ReportSummaryOut
    daily: list[DailyOut] = Field(
        ...,
        description="일별 외운 단어 수. 7일·월별은 기간의 모든 날(기록 없는 날 value=null), 전체는 기록 있는 날만",
    )
    stage_distribution: StageDistributionOut = Field(..., description="기간과 상관없는 현재 단어 상태")
