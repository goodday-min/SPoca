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


MAX_TOOL_ROUNDS = 3  # GPT가 도구를 연달아 부를 수 있는 최대 횟수 (무한 반복 방지)
MAX_TOOL_RESULT_CHARS = 6000


def complete_with_tools(messages: list[dict], tools: list[dict], run_tool) -> tuple[str, list[dict]]:
    """도구 호출(Function Calling)을 지원하는 대화.

    GPT가 도구를 부르겠다고 하면 run_tool(name, args) -> (결과 dict, 화면에 보일 이름) 을 실행해
    결과를 돌려주고, 최종 답변이 나올 때까지 반복한다. 반환: (답변, 호출 기록 [{name, arguments, label}]).
    서버가 도구를 지원하지 않아 첫 호출이 실패하면 도구 없이 일반 대화로 답한다.
    """
    work = list(messages)
    calls: list[dict] = []
    for round_no in range(MAX_TOOL_ROUNDS + 1):
        use_tools = round_no < MAX_TOOL_ROUNDS  # 마지막 바퀴는 도구 없이 답을 받는다
        try:
            kwargs = {"tools": tools, "tool_choice": "auto"} if use_tools else {}
            res = _client().chat.completions.create(model=settings.openai_model, messages=work, **kwargs)
        except LLMError:
            raise
        except Exception as e:
            if round_no == 0:
                logger.warning("도구 호출을 쓸 수 없어 일반 대화로 답해요: %s: %s", type(e).__name__, str(getattr(e, "message", e))[:300])
                return complete(messages), []
            logger.warning("GPT 호출 실패: %s: %s", type(e).__name__, str(getattr(e, "message", e))[:500])
            raise LLMError(f"GPT 호출에 실패했어요: {type(e).__name__}") from e
        msg = res.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            text = (msg.content or "").strip()
            if not text:
                raise LLMError("GPT가 빈 답변을 보냈어요")
            return text, calls
        work.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in tool_calls
                ],
            }
        )
        for c in tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
                if not isinstance(args, dict):
                    raise ValueError("인자가 객체가 아니에요")
            except ValueError:
                result, label = {"error": "도구 인자를 읽지 못했어요"}, c.function.name
                args = {}
            else:
                result, label = run_tool(c.function.name, args)
            logger.info("도구 호출: %s %s → %s", c.function.name, json.dumps(args, ensure_ascii=False), label)
            calls.append({"name": c.function.name, "arguments": args, "label": label})
            content = json.dumps(result, ensure_ascii=False)
            if len(content) > MAX_TOOL_RESULT_CHARS:
                content = content[:MAX_TOOL_RESULT_CHARS] + "…(길어서 잘렸어요)"
            work.append({"role": "tool", "tool_call_id": c.id, "content": content})
    raise LLMError("GPT가 답변을 만들지 못했어요")  # 도달하지 않음


def complete_vision(system: str, text: str, image_data_url: "str | list[str]") -> str:
    """사진 한 장(또는 여러 장)과 글을 Anthropic 호환 주소(/v1/messages)로 보내 답변 텍스트를 받는다.

    교육장 서버는 OpenAI 호환 주소에서 사진 입력을 막아 두었으므로 사진은 이쪽으로만 보낸다.
    image_data_url 은 'data:image/jpeg;base64,....' 모양이어야 한다(요청 검증에서 이미 확인).
    """
    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY가 설정되지 않았어요")
    urls = [image_data_url] if isinstance(image_data_url, str) else list(image_data_url)
    image_blocks = []
    for url in urls:
        header, _, data = url.partition(",")
        media_type = header.removeprefix("data:").removesuffix(";base64")
        image_blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    body = {
        "model": settings.anthropic_vision_model,
        "max_tokens": 4096,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": [*image_blocks, {"type": "text", "text": text}],
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
