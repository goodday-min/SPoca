"""책 사진 한 장으로 POST /api/words/scan 을 시험하는 스크립트. (추가 설치 없이 파이썬만으로 동작)

사용법 (프로젝트 폴더에서):
    python scripts/scan_image.py 사진.jpg
    python scripts/scan_image.py 사진.jpg --date 2026-10-09
    python scripts/scan_image.py 사진.jpg --url https://spoca-api.onrender.com

서버가 켜져 있어야 한다. 기본 주소는 내 컴퓨터(http://127.0.0.1:8000).
주의: 인식된 단어는 실제 단어장(Firestore)에 바로 등록된다. 시험 후 단어장에서 지운다.
"""
import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024  # 서버 한도(글자 7,000,000자)를 넘지 않도록 원본 약 5MB까지


def main() -> int:
    parser = argparse.ArgumentParser(description="책 사진으로 단어 스캔 등록 시험")
    parser.add_argument("image", help="사진 파일 (jpg, png, webp)")
    parser.add_argument("--date", help="등록일 YYYY-MM-DD (비우면 오늘)")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="서버 주소")
    args = parser.parse_args()

    path = Path(args.image)
    if not path.is_file():
        print(f"파일을 찾을 수 없어요: {path}")
        return 1
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        print("JPEG·PNG·WebP 사진만 쓸 수 있어요.")
        return 1
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        print(f"사진이 너무 커요({len(data) / 1024 / 1024:.1f}MB). 5MB 이하로 줄여서 다시 시도해 주세요.")
        return 1

    body = {"image": f"data:{mime};base64," + base64.b64encode(data).decode("ascii")}
    if args.date:
        body["registered_date"] = args.date

    req = urllib.request.Request(
        args.url.rstrip("/") + "/api/words/scan",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            out = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"실패 {e.code}: {e.read().decode('utf-8', 'replace')}")
        return 1
    except urllib.error.URLError as e:
        print(f"서버에 연결할 수 없어요: {e.reason}")
        return 1

    print(f"{out['count']}개 등록됨")
    for w in out["items"]:
        print(f"- {w['word']} | 뜻: {w['meaning'] or '(비어 있음)'} | 예문: {w['example'] or '(없음)'} | 등록일 {w['registered_date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
