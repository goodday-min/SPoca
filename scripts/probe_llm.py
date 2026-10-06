"""교육장 GPT 서버가 어떤 요청을 받아 주는지 하나씩 시험하는 진단 스크립트.

사용법 (backend 가상환경이 켜진 상태에서, 프로젝트 폴더에서):
    python scripts/probe_llm.py

backend/.env 의 OPENAI_* 설정을 그대로 쓴다. 키는 화면에 출력하지 않는다.
각 시험은 아주 짧은 요청이라 비용이 거의 들지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from openai import OpenAI  # noqa: E402

# 1x1 픽셀 PNG 사진 (사진 입력이 되는지만 보려는 용도)
TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
model = settings.openai_model
print(f"서버: {settings.openai_base_url}  모델: {model}\n")


def attempt(label, messages, **kwargs):
    try:
        res = client.chat.completions.create(model=kwargs.pop("model", model), messages=messages, **kwargs)
        text = (res.choices[0].message.content or "").strip().replace("\n", " ")
        print(f"[성공] {label} → {text[:80]!r}")
    except Exception as e:
        print(f"[실패] {label} → {type(e).__name__}: {str(getattr(e, 'message', e))[:300]}")


attempt("1) 글자만 (지금 채팅이 쓰는 방식)", [{"role": "user", "content": "Say OK"}])
attempt(
    "2) 글자만, 내용을 목록 형태로",
    [{"role": "user", "content": [{"type": "text", "text": "Say OK"}]}],
)
attempt(
    "3) 글자 + 사진(data URL)",
    [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What color is this image? Answer in one word."},
                {"type": "image_url", "image_url": {"url": TINY_PNG}},
            ],
        }
    ],
)

print("\n서버가 알려 주는 사용 가능한 모델:")
try:
    ids = sorted(m.id for m in client.models.list())
    print(", ".join(ids) if ids else "(목록 없음)")
except Exception as e:
    print(f"모델 목록을 가져오지 못했어요 → {type(e).__name__}: {str(getattr(e, 'message', e))[:200]}")
