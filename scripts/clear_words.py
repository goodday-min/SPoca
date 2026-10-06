"""단어장의 단어를 API로 지우는 스크립트. (시험 데이터 정리용, 추가 설치 없이 파이썬만으로 동작)

사용법 (프로젝트 폴더에서):
    python scripts/clear_words.py              # 지울 단어 목록만 보여 줌 (지우지 않음)
    python scripts/clear_words.py --yes        # 목록의 단어를 모두 지움
    python scripts/clear_words.py --source scan --yes   # 등록 경로가 scan 인 것만 지움
    python scripts/clear_words.py --url https://spoca-api.onrender.com --yes

서버가 켜져 있어야 한다. 기본 주소는 내 컴퓨터(http://127.0.0.1:8000).
주의: 지운 단어는 되돌릴 수 없다. 먼저 --yes 없이 목록을 확인한다.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="단어장 단어 지우기")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="서버 주소")
    parser.add_argument("--source", choices=["scan", "manual", "english_chat"], help="이 등록 경로의 단어만")
    parser.add_argument("--yes", action="store_true", help="확인 없이 실제로 지움 (없으면 목록만 보여 줌)")
    args = parser.parse_args()
    base = args.url.rstrip("/") + "/api/words"

    try:
        with urllib.request.urlopen(base, timeout=60) as res:
            items = json.loads(res.read().decode("utf-8"))["items"]
    except urllib.error.URLError as e:
        print(f"서버에 연결할 수 없어요: {getattr(e, 'reason', e)}")
        return 1
    if args.source:
        items = [w for w in items if w["source"] == args.source]
    if not items:
        print("지울 단어가 없어요.")
        return 0

    print(f"{len(items)}개:")
    for w in items:
        print(f"- {w['word']} (등록일 {w['registered_date']}, {w['source']})")
    if not args.yes:
        print("\n지우려면 같은 명령 끝에 --yes 를 붙여 다시 실행하세요.")
        return 0

    deleted = 0
    for w in items:
        req = urllib.request.Request(f"{base}/{w['id']}", method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=60).close()
            deleted += 1
        except urllib.error.HTTPError as e:
            print(f"지우지 못했어요: {w['word']} ({e.code})")
    print(f"\n{deleted}개 지웠어요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
