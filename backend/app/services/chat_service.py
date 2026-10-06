"""코칭 채팅: 요약 조회 → 시스템 프롬프트에 주입 → GPT 호출 → 대화 저장."""
from app.schemas.chat import ChatRequest
from app.schemas.conversation import ConversationCreate, Message
from app.services import conversation_service, llm_service

ROLE_PROMPT = (
    "당신은 영어 단어 암기 앱 '스포카'의 학습 코치입니다. 한국어 존댓말로 답하세요.\n"
    "아래 '학습 기록 요약'의 수치만 근거로 답하고, 요약에 없는 내용은 추측하지 말고 모른다고 말하세요.\n"
    "'외운 단어 수'는 그날 복습에서 패스한 단어 수입니다. 기록이 없는 날은 복습하지 않은 날이며 0으로 계산하지 않습니다."
)


def _fmt(v, unit: str = "") -> str:
    return "없음" if v is None else f"{v}{unit}"


def _stats_line(label: str, s: dict) -> str:
    p = s["period"]
    period = f"{p['start']} ~ {p['end']}" if p.get("start") else "기록 없음"
    return (
        f"- {label}({period}): 기록한 날 {s['count']}일, 하루 평균 {_fmt(s['average'], '개')}, "
        f"최대 {_fmt(s['max'], '개')}, 최소 {_fmt(s['min'], '개')}"
    )


def build_system_prompt(summary: dict) -> str:
    recent = summary["recent_7d"]
    lines = [
        ROLE_PROMPT,
        "",
        f"[학습 기록 요약] (오늘: {summary['today']}, 한국 시간)",
        _stats_line("전체", summary["overall"]),
        _stats_line("최근 7일(오늘 포함)", recent),
        f"- 직전 7일 하루 평균: {_fmt(recent['previous_average'], '개')}",
        f"- 추세(직전 7일 평균 대비): {recent['trend']}",
    ]
    daily = recent.get("daily")
    if daily:
        lines.append("- 최근 7일 날짜별 외운 단어 수 (기록 없는 날은 '기록 없음'):")
        for d in daily:
            mark = " (오늘)" if d["date"] == summary["today"] else ""
            lines.append(f"  · {d['date']}{mark}: {'기록 없음' if d['value'] is None else str(d['value']) + '개'}")
    return "\n".join(lines)


def chat(req: ChatRequest) -> dict:
    from app.services import summary_service  # 지연 import

    history: list[dict] = []
    if req.conversation_id:
        history = conversation_service.get(req.conversation_id)["messages"]  # 없으면 NotFoundError

    summary = summary_service.get_summary()
    system = {"role": "system", "content": build_system_prompt(summary)}
    user = {"role": "user", "content": req.message}

    reply = llm_service.complete([system, *history, user])  # 실패하면 여기서 중단 → 저장 안 함
    new_messages = [user, {"role": "assistant", "content": reply}]

    if req.conversation_id:
        conv = conversation_service.append(req.conversation_id, new_messages)
    else:
        conv = conversation_service.create(
            ConversationCreate(messages=[Message(**m) for m in new_messages])
        )
    return {"conversation_id": conv["id"], "title": conv["title"], "reply": reply}
