"""책 사진(1~3장)으로 영어 대화 백엔드 전체 흐름을 시험하는 스크립트. (추가 설치 없이 파이썬만으로 동작)

흐름: /api/english/scan → /api/english/chat (AI가 먼저 말함 → 내 말 몇 번) → /api/english/finish

사용법 (프로젝트 폴더에서):
    python scripts/english_demo.py 사진1.jpg
    python scripts/english_demo.py 사진1.jpg 사진2.jpg --level Advanced
    python scripts/english_demo.py 사진1.jpg --no-finish        # 단어 등록 없이 대화까지만

서버가 켜져 있어야 한다. 기본 주소는 내 컴퓨터(http://127.0.0.1:8000).
주의: 마지막 finish 단계에서 뽑힌 단어는 실제 단어장(Firestore)에 등록된다. 시험 후 지운다
      (python scripts/clear_words.py --yes 는 단어장 전체를 지우니 주의).
"""
import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
MY_LINES = ["I like it. It makes me curious.", "Can you tell me more about it?", "Thank you. That was fun. Goodbye!"]


def post(base: str, path: str, body: dict):
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"실패 {e.code}: {e.read().decode('utf-8', 'replace')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"서버에 연결할 수 없어요: {e.reason}")
        sys.exit(1)


def to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        sys.exit(f"JPEG·PNG·WebP 사진만 쓸 수 있어요: {path}")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        sys.exit(f"사진이 너무 커요({len(data) / 1024 / 1024:.1f}MB): {path}")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser(description="책 사진 영어 대화 흐름 시험")
    ap.add_argument("images", nargs="+", help="책 사진 1~3장")
    ap.add_argument("--level", choices=["Beginner", "Advanced"], default="Beginner")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--no-finish", action="store_true", help="마지막 단어 등록 단계를 건너뜀")
    args = ap.parse_args()
    if len(args.images) > 3:
        return print("사진은 최대 3장이에요.") or 1

    scan = post(args.url, "/api/english/scan", {"images": [to_data_url(Path(p)) for p in args.images]})
    print(f"[스캔] 문장 {scan['sentence_count']}개 인식\n  {scan['text'][:300]}{'…' if len(scan['text']) > 300 else ''}\n")

    messages: list[dict] = []
    first = post(args.url, "/api/english/chat", {"book_text": scan["text"], "level": args.level, "messages": messages})
    print(f"AI: {first['reply']}")
    messages.append({"role": "assistant", "content": first["reply"]})
    for line in MY_LINES:
        messages.append({"role": "user", "content": line})
        print(f"나: {line}")
        out = post(args.url, "/api/english/chat", {"book_text": scan["text"], "level": args.level, "messages": messages})
        print(f"AI: {out['reply']}" + ("   [AI가 대화를 마무리함]" if out["finished"] else ""))
        messages.append({"role": "assistant", "content": out["reply"]})
        if out["finished"]:
            break

    if args.no_finish:
        return 0
    fin = post(args.url, "/api/english/finish", {"book_text": scan["text"], "messages": messages})
    print(f"\n[종료] 단어 {fin['count']}개 등록")
    for w in fin["items"]:
        print(f"- {w['word']} | {w['meaning']} | {w['example']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
