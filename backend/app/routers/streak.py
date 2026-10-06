from fastapi import APIRouter

from app.schemas.review import StreakOut
from app.services import review_service

router = APIRouter(tags=["streak"])


@router.get("/streak", response_model=StreakOut)
def get_streak():
    """연속 학습 일수 (홈의 'N일 연속' 배지). 첫 복습을 마친 날부터 센다.
    복습을 끝낸 날은 +1, 복습 대상이 없는 날은 끊기지 않고 +1, 대상이 있는데 하지 않은 날은 끊긴다.
    복습할 단어가 있는데 아직 안 했으면 어제까지의 값(counts_today=false), 복습을 마치면 곧바로 오늘이 더해진 값."""
    return review_service.get_streak()
