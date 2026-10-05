"""대화 기록 검사 규칙과 제목 만들기 시험. (Firestore 없이)

실행 (backend 폴더에서): python -m tests.test_conversation
"""
from pydantic import ValidationError

from app.schemas.conversation import ConversationCreate
from app.services.conversation_service import make_title


def make(**kw):
    base = {"messages": [{"role": "user", "content": "최근 7일 어땠어?"}]}
    return ConversationCreate(**{**base, **kw})


def rejected(**kw) -> bool:
    try:
        make(**kw)
        return False
    except ValidationError:
        return True


def test_valid():
    c = make(title="  제목  ")
    assert make_title(c.title, c.messages) == "제목"


def test_auto_title():
    c = make()
    assert make_title(c.title, c.messages) == "최근 7일 어땠어?"
    long = make(messages=[{"role": "user", "content": "가" * 50}])
    assert make_title(long.title, long.messages) == "가" * 30 + "…"
    blank = make(title="   ")
    assert make_title(blank.title, blank.messages) == "최근 7일 어땠어?"


def test_title_skips_assistant_first():
    c = make(messages=[{"role": "assistant", "content": "안녕하세요"}, {"role": "user", "content": "질문\n둘째줄"}])
    assert make_title(None, c.messages) == "질문 둘째줄"


def test_rejects_bad_input():
    assert rejected(messages=[])  # 메시지가 하나도 없음
    assert rejected(messages=[{"role": "system", "content": "x"}])  # 허용하지 않는 role
    assert rejected(messages=[{"role": "user", "content": ""}])  # 빈 메시지
    assert rejected(messages=[{"role": "user", "content": "a" * 4001}])  # 너무 긴 메시지
    assert rejected(title="a" * 101)  # 너무 긴 제목


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("통과:", t.__name__)
    print(f"{len(tests)}개 모두 통과")
