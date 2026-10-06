"""서버의 모든 모델에 작은 사진을 보내, 사진 입력이 되는 모델을 찾는 진단 스크립트.

사용법 (backend 가상환경이 켜진 상태에서, 프로젝트 폴더에서):
    python scripts/probe_vision.py

키는 출력하지 않는다. 모델마다 아주 짧은 요청 1번씩이라 비용이 거의 들지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402
from openai import OpenAI  # noqa: E402

# 2x2 빨간색 PNG (사진 입력이 되는지만 보려는 용도)
RED_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg=="

client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, timeout=60)
print(f"서버: {settings.openai_base_url}\n")

ids = sorted(m.id for m in client.models.list())
for model in ids:
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this image? Answer in one word."},
                    {"type": "image_url", "image_url": {"url": RED_PNG}},
                ],
            }],
        )
        text = (res.choices[0].message.content or "").strip().replace("\n", " ")
        print(f"[성공] {model} → {text[:60]!r}")
    except Exception as e:
        print(f"[실패] {model} → {type(e).__name__}: {str(getattr(e, 'message', e))[:120]}")
