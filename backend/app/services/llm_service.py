"""GPT 호출. 교육장 OpenAI 호환 서버(OPENAI_BASE_URL)로 보낸다."""
from functools import lru_cache

from app.core.config import settings


class LLMError(Exception):
    """GPT 호출 실패(키 누락, 서버 오류, 빈 답변 등)"""


@lru_cache
def _client():
    from openai import OpenAI  # 지연 import

    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY가 설정되지 않았어요")
    return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


def complete(messages: list[dict]) -> str:
    """messages([{role, content}])를 보내 답변 텍스트를 받는다."""
    try:
        res = _client().chat.completions.create(model=settings.openai_model, messages=messages)
    except LLMError:
        raise
    except Exception as e:  # 네트워크·인증·서버 오류를 한 종류로 묶는다
        raise LLMError(f"GPT 호출에 실패했어요: {type(e).__name__}") from e
    text = (res.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("GPT가 빈 답변을 보냈어요")
    return text
