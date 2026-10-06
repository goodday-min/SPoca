from fastapi import APIRouter, HTTPException, Query

from app.schemas.report import Period, ReportOut
from app.services import report_service
from app.services.report_service import InvalidMonthError

router = APIRouter(prefix="/report", tags=["report"])


@router.get("", response_model=ReportOut)
def get_report(
    period: Period = Query("7d", description="7d(최근 7일) / month(월별) / all(전체)"),
    month: str | None = Query(None, description="month 보기일 때 YYYY-MM. 안 보내면 이번 달. 다른 보기에서는 무시"),
):
    """학습 리포트: 기간 요약 + 일별 그래프 데이터 + 단어 단계 분포. 추세는 7d에서만 값이 있다."""
    try:
        if period == "month" and month is not None:
            report_service.parse_month(month)  # 형식 검사 (DB 접근 전에)
        return report_service.get_report(period, month)
    except InvalidMonthError as e:
        raise HTTPException(422, str(e))
