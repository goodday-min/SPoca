"""도구 호출(Function Calling) 시험: 요약에 없는 질문을 보내고, AI가 어떤 도구를 불렀는지 확인한다.

사용법 (서버가 켜져 있어야 한다. 기본 주소 http://127.0.0.1:8000):
    python scripts/chat_tools_demo.py                       # 예시 질문 3개
    python scripts/chat_tools_demo.py "지난달 15일에 몇 개 외웠어?"
    python scripts/chat_tools_demo.py --base https://spoca-api.onrender.com

결과의 'tools' 가 비어 있지 않으면 도구 호출이 일어난 것이다.
항상 비어 있고 답이 "모르겠어요"라면 교육장 서버가 도구 호출을 지원하지 않는 것일 수 있다
(이 경우 서버 터미널에 '도구 호출을 쓸 수 없어 일반 대화로 답해요' 경고가 찍힌다).
주의: 시험 질문도 대화로 저장된다(AI코치의 '지난 대화'에서 지울 수 있다).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

EXAMPLES = ["2026년 9월 15일에 몇 개 외웠는지 조회해서 알려 줘", "내 최장 연속 기록이랑 가장 잘한 요일 알려 줘", "지난 대화 목록을 보고 내가 예전에 뭘 물어봤는지 알려 줘"]


def post(base: str, message: str) -> dict:
    req = urllib.request.Request(
        base.rstrip("/") + "/api/chat",
        data=json.dumps({"message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"오류 {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"서버에 연결할 수 없어요: {e.reason}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", nargs="*")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    for q in args.questions or EXAMPLES:
        out = post(args.base, q)
        print(f"\n질문: {q}\n조회한 것: {out['tools'] or '(없음)'}\n답변: {out['reply']}")


if __name__ == "__main__":
    main()
