from fastapi import APIRouter, HTTPException, status

from app.schemas.english import (
    EnglishChatOut,
    EnglishChatRequest,
    EnglishFinishOut,
    EnglishFinishRequest,
    EnglishScanOut,
    EnglishScanRequest,
)
from app.services import english_service
from app.services.english_service import NoTextFoundError
from app.services.llm_service import LLMError

router = APIRouter(prefix="/english", tags=["english"])

NO_TEXT_MESSAGE = "글자를 읽지 못했어요. 글자가 잘 보이게 다시 찍어 주세요"


@router.post("/scan", response_model=EnglishScanOut)
def scan_book(payload: EnglishScanRequest):
    """책 사진 1~3장을 합쳐 읽는다. 저장하지 않고 인식한 글만 돌려준다. 못 읽으면 422, 사진 읽기 실패는 502."""
    try:
        return english_service.scan(payload)
    except NoTextFoundError:
        raise HTTPException(422, NO_TEXT_MESSAGE)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


@router.post("/chat", response_model=EnglishChatOut)
def chat(payload: EnglishChatRequest):
    """영어 대화 한 턴. messages가 비면 AI가 먼저 말을 건다. 대화는 저장하지 않는다. GPT 실패는 502."""
    try:
        return english_service.chat(payload)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))


@router.post("/finish", response_model=EnglishFinishOut, status_code=status.HTTP_201_CREATED)
def finish(payload: EnglishFinishRequest):
    """대화 종료: 핵심 단어(최대 10개)를 뽑아 단어장에 자동 등록(등록일 오늘, source=english_chat). 대화는 저장하지 않는다."""
    try:
        return english_service.finish(payload)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
