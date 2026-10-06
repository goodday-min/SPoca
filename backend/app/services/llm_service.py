"""GPT 호출. 교육장 OpenAI 호환 서버(OPENAI_BASE_URL)로 보낸다."""
import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")  # uvicorn 터미널에 그대로 보이게


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
        # 사용자에게는 짧게 알리고, 원인(서버가 돌려준 메시지)은 서버 로그에만 남긴다.
        logger.warning("GPT 호출 실패: %s: %s", type(e).__name__, str(getattr(e, "message", e))[:500])
        raise LLMError(f"GPT 호출에 실패했어요: {type(e).__name__}") from e
    text = (res.choices[0].message.content or "").strip()
    if not text:
        raise LLMError("GPT가 빈 답변을 보냈어요")
    return text


def complete_vision(system: str, text: str, image_data_url: str) -> str:
    """사진 한 장과 글을 Anthropic 호환 주소(/v1/messages)로 보내 답변 텍스트를 받는다.

    교육장 서버는 OpenAI 호환 주소에서 사진 입력을 막아 두었으므로 사진은 이쪽으로만 보낸다.
    image_data_url 은 'data:image/jpeg;base64,....' 모양이어야 한다(요청 검증에서 이미 확인).
    """
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY가 설정되지 않았어요")
    header, _, data = image_data_url.partition(",")
    media_type = header.removeprefix("data:").removesuffix(";base64")
    body = {
        "model": settings.anthropic_vision_model,
        "max_tokens": 4096,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                    {"type": "text", "text": text},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        settings.anthropic_base_url.rstrip("/") + "/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": settings.anthropic_api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            out = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning("사진 읽기 실패: HTTP %s %s", e.code, e.read().decode("utf-8", "replace")[:500])
        raise LLMError(f"사진 읽기에 실패했어요: HTTP {e.code}") from e
    except Exception as e:
        logger.warning("사진 읽기 실패: %s: %s", type(e).__name__, str(e)[:500])
        raise LLMError(f"사진 읽기에 실패했어요: {type(e).__name__}") from e
    answer = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
    if not answer:
        raise LLMError("사진 읽기에서 빈 답변이 왔어요")
    return answer
