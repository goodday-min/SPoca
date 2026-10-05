from fastapi import APIRouter, HTTPException, Query, Response, status

from app.schemas.data import DataCreate, DataListOut, DataOut, DataUpdate
from app.schemas.summary import SummaryOut
from app.services import data_service
from app.services import summary_service
from app.services.data_service import DataNotFoundError, DuplicateDateError

router = APIRouter(prefix="/data", tags=["data"])

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
DUPLICATE_MESSAGE = "이미 기록이 있어요"
NOT_FOUND_MESSAGE = "해당 기록을 찾을 수 없어요"


@router.post("", response_model=DataOut, status_code=status.HTTP_201_CREATED)
def create_data(payload: DataCreate):
    """학습 기록 추가. 같은 날짜가 이미 있으면 409."""
    try:
        return data_service.create(payload)
    except DuplicateDateError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_MESSAGE)


@router.get("", response_model=DataListOut)
def list_data(
    limit: int = Query(20, ge=1, le=100, description="한 번에 불러올 개수"),
    cursor: str | None = Query(None, description="이 날짜보다 이전 기록부터 불러온다 (더 보기)"),
    start: str | None = Query(None, pattern=DATE_PATTERN, description="이 날짜 이후(포함) 기록만 (YYYY-MM-DD)"),
    end: str | None = Query(None, pattern=DATE_PATTERN, description="이 날짜 이전(포함) 기록만 (YYYY-MM-DD)"),
):
    """학습 기록 목록 (최신 날짜 순). start/end 로 기간을 좁힐 수 있다."""
    return data_service.list_items(limit, cursor, start, end)


@router.get("/summary", response_model=SummaryOut)
def get_data_summary():
    """학습 기록 요약 (전체 + 최근 7일, 추세). 코칭 채팅의 프롬프트에 주입할 때도 쓴다."""
    return summary_service.get_summary()


@router.put("/{doc_id}", response_model=DataOut)
def update_data(doc_id: str, payload: DataUpdate):
    """학습 기록 수정. 바꾼 날짜가 다른 기록과 겹치면 409."""
    try:
        return data_service.update(doc_id, payload)
    except DataNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)
    except DuplicateDateError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_MESSAGE)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data(doc_id: str):
    """학습 기록 삭제"""
    try:
        data_service.delete(doc_id)
    except DataNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
