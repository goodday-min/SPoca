from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.schemas.word import WordCreate, WordListOut, WordOut, WordScanOut, WordScanRequest, WordUpdate
from app.services import word_scan_service, word_service
from app.services.llm_service import LLMError
from app.services.word_scan_service import NoWordsFoundError
from app.services.word_service import PastRegisteredDateError, WordNotFoundError

router = APIRouter(prefix="/words", tags=["words"])

PAST_DATE_MESSAGE = "등록일: 오늘이나 이후 날짜만 선택할 수 있어요"
NOT_FOUND_MESSAGE = "해당 단어를 찾을 수 없어요"
NO_WORDS_MESSAGE = "단어를 찾지 못했어요. 글자가 잘 보이게 다시 찍어 주세요"


@router.post("", response_model=WordOut, status_code=status.HTTP_201_CREATED)
def create_word(payload: WordCreate):
    """단어 직접 등록. 등록일을 비우면 오늘, 오늘보다 이전 날짜는 422.
    새 단어는 항상 New 단계·복습 중 상태로 시작한다."""
    try:
        return word_service.create(payload, source="manual")
    except PastRegisteredDateError:
        raise HTTPException(422, PAST_DATE_MESSAGE)


@router.post("/scan", response_model=WordScanOut, status_code=status.HTTP_201_CREATED)
def scan_words(payload: WordScanRequest):
    """책 사진 한 장에서 단어를 읽어 확인 없이 바로 등록한다.
    뜻이 사진에 없으면 비워 둔다. 단어를 못 찾으면 422, GPT 호출 실패는 502."""
    try:
        return word_scan_service.scan(payload)
    except PastRegisteredDateError:
        raise HTTPException(422, PAST_DATE_MESSAGE)
    except NoWordsFoundError:
        raise HTTPException(422, NO_WORDS_MESSAGE)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


@router.get("", response_model=WordListOut)
def list_words(
    sort: Literal["latest", "stage"] = Query(
        "latest",
        description="latest: 최신 등록순(등록일이 나중인 단어 먼저) / stage: 단계순(New→V1→V2→V3→Master, 끝난 단어는 맨 아래)",
    ),
):
    """단어 목록. 모든 단어를 한 번에 돌려준다."""
    return word_service.list_items(sort)


@router.put("/{doc_id}", response_model=WordOut)
def update_word(doc_id: str, payload: WordUpdate):
    """단어·뜻·예문 수정. 단계·상태·등록일은 보내도 바뀌지 않는다."""
    try:
        return word_service.update(doc_id, payload)
    except WordNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word(doc_id: str):
    """단어 삭제 (바로 삭제)"""
    try:
        word_service.delete(doc_id)
    except WordNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
