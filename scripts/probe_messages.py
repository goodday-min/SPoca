"""Anthropic 호환 주소(/v1/messages)로 사진을 보내 보는 진단 스크립트. (추가 설치 없이 파이썬만으로 동작)

사용법 (backend 가상환경이 켜진 상태에서, 프로젝트 폴더에서):
    python scripts/probe_messages.py

Anthropic 호환 키는 지금 쓰는 키와 다르다. backend/.env 에 한 줄 추가해 둔다:
    ANTHROPIC_API_KEY=발급받은키
주소는 OPENAI_BASE_URL 에서 가져오고, 인증은 문서대로 x-api-key 머리글을 쓴다.
키는 출력하지 않는다. 글자만·사진 두 경우를 본다.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import settings  # noqa: E402


def read_anthropic_key() -> str:
    """backend/.env 에서 ANTHROPIC_API_KEY 를 읽는다(없으면 빈 글자)."""
    env = Path(__file__).resolve().parents[1] / "backend" / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


KEY = read_anthropic_key()
if not KEY:
    sys.exit("backend/.env 에 ANTHROPIC_API_KEY=... 한 줄을 먼저 넣어 주세요.")

RED_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AARAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg=="
URL = settings.openai_base_url.rstrip("/") + "/messages"
MODELS = ["claude-haiku-4", "claude-sonnet-4", "claude-opus-4-7"]

print(f"주소: {URL}\n")


def call(model, content):
    headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": KEY}
    body = {"model": model, "max_tokens": 50, "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            out = json.loads(res.read().decode())
        return "성공", "".join(b.get("text", "") for b in out.get("content", []))[:60]
    except urllib.error.HTTPError as e:
        return f"실패 {e.code}", e.read().decode("utf-8", "replace")[:160]
    except Exception as e:
        return "실패", f"{type(e).__name__}: {e}"


text_only = [{"type": "text", "text": "Say OK"}]
with_image = [
    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": RED_PNG_B64}},
    {"type": "text", "text": "What color is this image? Answer in one word."},
]
for model in MODELS:
    s1, t1 = call(model, text_only)
    s2, t2 = call(model, with_image)
    print(f"{model}\n   글자만: {s1} {t1!r}\n   사진:   {s2} {t2!r}")
