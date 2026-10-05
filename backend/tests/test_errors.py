"""422 메시지 변환 테스트 (FastAPI 없이, Pydantic 오류 목록으로)"""
from pydantic import ValidationError

from app.core.errors import format_validation_errors
from app.schemas.chat import ChatRequest
from app.schemas.conversation import ConversationCreate
from app.schemas.data import DataCreate


def msg(model, payload) -> str:
    try:
        model(**payload)
    except ValidationError as e:
        # FastAPI는 loc 앞에 "body"를 붙이므로 같게 만든다
        errs = [{**x, "loc": ("body", *x["loc"])} for x in e.errors()]
        return format_validation_errors(errs)
    raise AssertionError("검증을 통과하면 안 됨")


def test_data_errors():
    assert msg(DataCreate, {"date": "2026-13-45", "value": 3}) == "날짜: 존재하지 않는 날짜예요. YYYY-MM-DD 형식으로 입력해 주세요."
    assert msg(DataCreate, {"date": "20261005", "value": 3}) == "날짜: YYYY-MM-DD 형식으로 입력해 주세요"
    assert msg(DataCreate, {"date": "2026-10-05", "value": -1}) == "외운 단어 수: 0 이상이어야 해요"
    assert msg(DataCreate, {"date": "2026-10-05", "value": 1.5}) == "외운 단어 수: 정수여야 해요"
    assert msg(DataCreate, {"date": "2026-10-05", "value": "5"}) == "외운 단어 수: 정수여야 해요"
    assert msg(DataCreate, {"date": "2026-10-05", "value": 3, "memo": "가" * 201}) == "메모: 200자 이하로 입력해 주세요"
    assert msg(DataCreate, {"value": 3}) == "날짜: 꼭 필요해요"


def test_chat_and_conversation_errors():
    assert msg(ChatRequest, {"message": "   "}) == "질문: 질문을 입력해 주세요"
    assert msg(ChatRequest, {"message": "x" * 4001}) == "질문: 4000자 이하로 입력해 주세요"
    assert msg(ConversationCreate, {"messages": []}) == "메시지 목록: 1개 이상이어야 해요"
    assert msg(ConversationCreate, {"messages": [{"role": "bot", "content": "hi"}]}) == "말한 사람: 허용되지 않는 값이에요"
    assert msg(ConversationCreate, {"messages": [{"role": "user", "content": ""}]}) == "메시지 내용: 비워 둘 수 없어요"


def test_special_cases():
    assert format_validation_errors([{"type": "json_invalid", "loc": ("body", 1), "msg": "x"}]) == "요청 본문이 올바른 JSON이 아니에요"
    assert format_validation_errors([{"type": "missing", "loc": ("body",), "msg": "x"}]) == "요청 본문이 필요해요"
    assert format_validation_errors([{"type": "less_than_equal", "loc": ("query", "limit"), "msg": "x", "ctx": {"le": 100}}]) == "불러올 개수: 100 이하여야 해요"
    assert format_validation_errors([]) == "입력값이 올바르지 않아요"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("통과:", name)
    print("모두 통과")
