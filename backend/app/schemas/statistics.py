"""학습 통계(statistics) 응답 모양: 최장 연속 기록 + 요일별 평균."""
from pydantic import BaseModel, Field


class StreakOut(BaseModel):
    days: int = Field(..., description="기록이 하루도 빠지지 않고 이어진 가장 긴 날 수 (기록이 없으면 0)")
    start: str | None = Field(None, description="그 구간의 첫 날 (YYYY-MM-DD)")
    end: str | None = Field(None, description="그 구간의 마지막 날 (YYYY-MM-DD)")


class WeekdayOut(BaseModel):
    weekday: str = Field(..., description="월·화·수·목·금·토·일")
    average: float | None = Field(None, description="그 요일에 기록이 있는 날들의 평균 (기록이 없으면 null)")
    count: int = Field(..., description="그 요일의 기록 개수")


class StatisticsOut(BaseModel):
    period: dict = Field(..., description="계산에 쓴 기간 {start, end} (제한이 없으면 둘 다 null)")
    longest_streak: StreakOut
    weekday_average: list[WeekdayOut] = Field(..., description="월요일부터 일요일까지 항상 7개")
    best_weekday: str | None = Field(None, description="평균이 가장 높은 요일 (기록이 없으면 null, 같으면 먼저 오는 요일)")
