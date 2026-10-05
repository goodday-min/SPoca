"""요약(summary) 응답 모양. 코칭 채팅의 시스템 프롬프트와 화면의 요약 카드에 쓰인다."""
from typing import Literal

from pydantic import BaseModel, Field

Trend = Literal["증가", "감소", "유지", "비교 불가"]


class PeriodOut(BaseModel):
    start: str | None = Field(None, description="시작일 (YYYY-MM-DD)")
    end: str | None = Field(None, description="종료일 (YYYY-MM-DD)")


class StatsOut(BaseModel):
    period: PeriodOut
    count: int = Field(..., description="기록이 있는 날의 수")
    average: float | None = Field(None, description="평균 (기록이 있는 날만, 소수 첫째 자리)")
    max: int | None = None
    min: int | None = None


class RecentStatsOut(StatsOut):
    previous_average: float | None = Field(None, description="그 이전 7일의 평균 (기록이 있는 날만)")
    trend: Trend = Field(..., description="이전 7일 평균 대비 증가/감소/유지, 비교할 수 없으면 '비교 불가'")


class SummaryOut(BaseModel):
    today: str = Field(..., description="계산 기준일 (한국 시간 오늘)")
    overall: StatsOut = Field(..., description="전체 기간 요약")
    recent_7d: RecentStatsOut = Field(..., description="최근 7일(오늘 포함) 요약과 추세")
