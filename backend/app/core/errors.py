"""입력 검증 오류(422)를 사람이 읽을 수 있는 한국어 한 줄로 바꾼다.

모든 오류 응답이 {"detail": "한국어 문구"} 한 가지 모양이 되도록 맞춘다.
(404·409는 라우터에서 이미 이 모양으로 보낸다.) 오류가 여러 개면 첫 번째만 보여 준다.
"""
FIELD_LABELS = {
    "date": "날짜",
    "value": "외운 단어 수",
    "memo": "메모",
    "title": "제목",
    "messages": "메시지 목록",
    "content": "메시지 내용",
    "role": "말한 사람",
    "message": "질문",
    "conversation_id": "대화 ID",
    "limit": "불러올 개수",
    "cursor": "커서",
    "start": "시작일",
    "end": "종료일",
    "word": "단어",
    "meaning": "뜻",
    "example": "예문",
    "registered_date": "등록일",
    "sort": "정렬 기준",
    "image": "사진",
    "images": "사진",
    "book_text": "책 내용",
    "level": "난이도",
}
FALLBACK = "입력값이 올바르지 않아요"


def _label(loc: tuple) -> str | None:
    """loc 맨 뒤쪽의 문자열 이름(숫자 인덱스 제외)을 한국어 이름으로."""
    names = [p for p in loc if isinstance(p, str) and p not in ("body", "query", "path")]
    if not names:
        return None
    return FIELD_LABELS.get(names[-1], names[-1])


def _reason(err: dict) -> str:
    t, ctx, msg = err.get("type", ""), err.get("ctx") or {}, err.get("msg", "")
    loc = err.get("loc", ())
    if "image" in loc:  # 사진은 글자 수가 아니라 크기·형식으로 안내한다
        if t == "string_too_long":
            return "사진이 너무 커요. 더 작게 줄여서 올려 주세요"
        if t == "string_pattern_mismatch":
            return "JPEG·PNG·WebP 사진만 올릴 수 있어요"
    if t == "missing":
        return "꼭 필요해요"
    if t == "string_too_long":
        return f"{ctx.get('max_length')}자 이하로 입력해 주세요"
    if t == "string_too_short":
        return "비워 둘 수 없어요"
    if t == "too_short":
        return f"{ctx.get('min_length')}개 이상이어야 해요"
    if t == "too_long":
        return f"{ctx.get('max_length')}개 이하여야 해요"
    if t in ("greater_than_equal", "greater_than"):
        bound = ctx.get("ge", ctx.get("gt"))
        return f"{bound} 이상이어야 해요" if t == "greater_than_equal" else f"{bound}보다 커야 해요"
    if t in ("less_than_equal", "less_than"):
        bound = ctx.get("le", ctx.get("lt"))
        return f"{bound} 이하여야 해요" if t == "less_than_equal" else f"{bound}보다 작아야 해요"
    if t in ("int_type", "int_parsing", "int_from_float"):
        return "정수여야 해요"
    if t == "string_type":
        return "글자여야 해요"
    if t == "string_pattern_mismatch":
        return "YYYY-MM-DD 형식으로 입력해 주세요" if any(k in loc for k in ("date", "registered_date", "start", "end", "cursor")) else "형식이 올바르지 않아요"
    if t == "literal_error":
        return "허용되지 않는 값이에요"
    if t == "value_error":  # 우리가 validator에서 직접 쓴 한국어 문구
        return msg.removeprefix("Value error, ")
    return "올바르지 않은 값이에요"


def format_validation_errors(errors: list[dict]) -> str:
    if not errors:
        return FALLBACK
    err = errors[0]
    if err.get("type") == "json_invalid":
        return "요청 본문이 올바른 JSON이 아니에요"
    loc = tuple(err.get("loc", ()))
    if err.get("type") == "missing" and loc == ("body",):
        return "요청 본문이 필요해요"
    label = _label(loc)
    reason = _reason(err)
    return f"{label}: {reason}" if label else reason


def register_error_handlers(app) -> None:
    from fastapi import Request  # 지연 import: 변환 함수는 FastAPI 없이도 테스트할 수 있게
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": format_validation_errors(exc.errors())})
