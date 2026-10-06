from fastapi import APIRouter, HTTPException, status

from app.schemas.review import ReviewCompleteOut, ReviewCompleteRequest, ReviewTodayOut
from app.services import review_service
from app.services.review_service import AlreadyReviewedError, InvalidTappedWordsError, NothingToReviewError

router = APIRouter(prefix="/review", tags=["review"])

ALREADY_MESSAGE = "오늘은 이미 복습을 마쳤어요"
NOTHING_MESSAGE = "오늘 복습할 단어가 없어요"
INVALID_TAPPED_MESSAGE = "오늘 복습 대상이 아닌 단어가 포함되어 있어요"


@router.get("/today", response_model=ReviewTodayOut)
def review_today():
    """오늘 복습할 단어(한국 시간 기준). 복습 중인 단어 중 현재 단계의 복습일이 오늘이거나 지난 것.
    등록일이 미래인 단어는 나오지 않고, 복습일을 놓친 단어는 지금 단계로 한 번만 나온다.
    completed_today 가 true 면 오늘 복습을 이미 마친 것이다(하루 한 번). 이때 items 는 비어 있다."""
    return review_service.today_review()


@router.post("/complete", response_model=ReviewCompleteOut, status_code=status.HTTP_201_CREATED)
def review_complete(payload: ReviewCompleteRequest):
    """복습 완료. 탭한 단어(tapped_ids)는 못 외움 → 다음 단계(Master면 '못 외움'으로 종료),
    탭하지 않은 오늘 대상 단어는 패스(외움, 끝). 패스한 수는 오늘 학습 기록의 value로 자동 기록된다(메모 유지).
    하루 한 번만 가능(두 번째는 409), 오늘 대상이 없으면 409, 대상이 아닌 ID가 있으면 422."""
    try:
        return review_service.complete(payload.tapped_ids)
    except AlreadyReviewedError:
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_MESSAGE)
    except NothingToReviewError:
        raise HTTPException(status.HTTP_409_CONFLICT, NOTHING_MESSAGE)
    except InvalidTappedWordsError:
        raise HTTPException(422, INVALID_TAPPED_MESSAGE)
