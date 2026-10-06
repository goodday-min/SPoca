"""AI코치가 부를 수 있는 조회 도구 (보너스 5.1 A. Function Calling).

GPT에는 TOOLS(이름·설명·인자 모양)만 알려 주고, 실제 조회는 run_tool 이 서버에서 실행한다.
조회 함수는 읽기 전용이고, 결과는 GPT가 읽는 '데이터'일 뿐 지시가 아니다.
"""
import re
from datetime import date, timedelta, timezone

KST = timezone(timedelta(hours=9))

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_RECORDS = 100  # 한 번에 돌려줄 기록 수
MAX_CONVERSATIONS = 20
MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 500

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_records",
            "description": "기간 안의 날짜별 학습 기록(그날 외운 단어 수, 메모)을 날짜순으로 조회한다. 요약에 없는 특정 날짜나 긴 기간을 물을 때 쓴다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "시작 날짜 YYYY-MM-DD (포함)"},
                    "end": {"type": "string", "description": "끝 날짜 YYYY-MM-DD (포함). 하루만 보려면 start와 같게"},
                },
                "required": ["start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "기간의 통계(기록한 날 수, 평균·최대·최소), 최장 연속 기록, 요일별 평균, 가장 잘한 요일을 계산해 돌려준다. 기간을 비우면 전체 기록 기준.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "시작 날짜 YYYY-MM-DD (선택)"},
                    "end": {"type": "string", "description": "끝 날짜 YYYY-MM-DD (선택)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "지난 AI코치 대화 목록(제목, 마지막 대화 날짜, 메시지 수, id)을 최근순으로 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "가져올 개수 (1~20, 기본 10)"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversation",
            "description": "지난 대화 한 개의 내용(최근 메시지 위주)을 조회한다. id는 list_conversations 로 먼저 찾는다.",
            "parameters": {
                "type": "object",
                "properties": {"conversation_id": {"type": "string", "description": "대화 id"}},
                "required": ["conversation_id"],
            },
        },
    },
]


def _md(iso: str) -> str:
    _, m, d = iso.split("-")
    return f"{int(m)}/{int(d)}"


def _check_range(args: dict, required: bool) -> tuple[str | None, str | None, str | None]:
    """(start, end, 오류 문구). 날짜 모양과 순서를 확인한다."""
    start, end = args.get("start"), args.get("end")
    if required and (not start or not end):
        return None, None, "start 와 end 날짜(YYYY-MM-DD)가 필요해요"
    for v in (start, end):
        if v:
            if not isinstance(v, str) or not DATE_RE.match(v):
                return None, None, "날짜는 YYYY-MM-DD 모양이어야 해요"
            try:
                date.fromisoformat(v)
            except ValueError:
                return None, None, "존재하지 않는 날짜예요"
    if start and end and start > end:
        return None, None, "start 가 end 보다 늦을 수 없어요"
    return start or None, end or None, None


def _range_label(start: str | None, end: str | None) -> str:
    if start and end:
        return _md(start) if start == end else f"{_md(start)}~{_md(end)}"
    return "전체"


def _get_records(args: dict) -> tuple[dict, str]:
    from app.services import data_service

    start, end, err = _check_range(args, required=True)
    if err:
        return {"error": err}, "학습 기록"
    rows = data_service.export_items(start, end)
    truncated = len(rows) > MAX_RECORDS
    return (
        {
            "period": {"start": start, "end": end},
            "count": len(rows),
            "truncated": truncated,
            "records": [{"date": r["date"], "value": r["value"], "memo": r["memo"]} for r in rows[:MAX_RECORDS]],
            "note": "기록이 없는 날짜는 목록에 없다 (복습하지 않은 날, 0으로 계산하지 않는다)",
        },
        f"기간별 학습 기록({_range_label(start, end)})",
    )


def _get_statistics(args: dict) -> tuple[dict, str]:
    from app.services import data_service, statistics_service
    from app.services.summary_service import _stats

    start, end, err = _check_range(args, required=False)
    if err:
        return {"error": err}, "학습 통계"
    rows = data_service.export_items(start, end)
    stat = statistics_service.build_statistics(rows, start, end)
    base = _stats([r["value"] for r in rows])
    result = {
        "period": stat["period"],
        "recorded_days": base["count"],
        "average": base["average"],
        "max": base["max"],
        "min": base["min"],
        "longest_streak": stat["longest_streak"],
        "weekday_average": [w for w in stat["weekday_average"] if w["count"]],
        "best_weekday": stat["best_weekday"],
    }
    return result, f"학습 통계({_range_label(start, end)})"


def _list_conversations(args: dict) -> tuple[dict, str]:
    from app.services import conversation_service

    try:
        limit = int(args.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, MAX_CONVERSATIONS))
    items = conversation_service.list_items(limit)
    return (
        {
            "conversations": [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "last_date": c["updated_at"].astimezone(KST).strftime("%Y-%m-%d") if hasattr(c["updated_at"], "astimezone") else str(c["updated_at"])[:10],
                    "message_count": c["message_count"],
                }
                for c in items
            ]
        },
        "지난 대화 목록",
    )


def _get_conversation(args: dict) -> tuple[dict, str]:
    from app.services import conversation_service

    cid = args.get("conversation_id")
    if not isinstance(cid, str) or not cid.strip():
        return {"error": "conversation_id 가 필요해요"}, "지난 대화 내용"
    try:
        conv = conversation_service.get(cid.strip())
    except conversation_service.ConversationNotFoundError:
        return {"error": "해당 대화를 찾을 수 없어요"}, "지난 대화 내용"
    msgs = conv["messages"][-MAX_MESSAGES:]
    return (
        {
            "title": conv["title"],
            "message_count": conv["message_count"],
            "messages": [{"role": m["role"], "content": m["content"][:MAX_MESSAGE_CHARS]} for m in msgs],
        },
        f"지난 대화 내용({conv['title']})",
    )


_HANDLERS = {
    "get_records": _get_records,
    "get_statistics": _get_statistics,
    "list_conversations": _list_conversations,
    "get_conversation": _get_conversation,
}


def run_tool(name: str, args: dict) -> tuple[dict, str]:
    """도구를 실행해 (결과, 화면에 보일 이름)을 돌려준다. 알 수 없는 도구·실행 오류는 error 로 알려 GPT가 알아서 답하게 한다."""
    handler = _HANDLERS.get(name)
    if not handler:
        return {"error": f"알 수 없는 도구예요: {name}"}, name
    try:
        return handler(args)
    except Exception as e:  # 조회 실패가 대화 전체를 막지 않게 한다
        return {"error": f"조회에 실패했어요: {type(e).__name__}"}, name
