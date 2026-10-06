"""도구 호출(Function Calling) 단위 테스트 (Firestore·GPT 없이)"""
import json
from types import SimpleNamespace as NS

import pytest

from app.services import chat_tools, data_service, llm_service

ROWS = [
    {"date": "2026-09-15", "value": 12, "memo": "굿"},
    {"date": "2026-09-16", "value": 4, "memo": ""},
    {"date": "2026-09-22", "value": 9, "memo": ""},
]


# ---------- 도구 실행 ----------
def test_get_records_range_and_label(monkeypatch):
    seen = {}

    def fake(start, end):
        seen["r"] = (start, end)
        return ROWS[:1]

    monkeypatch.setattr(data_service, "export_items", fake)
    result, label = chat_tools.run_tool("get_records", {"start": "2026-09-15", "end": "2026-09-15"})
    assert seen["r"] == ("2026-09-15", "2026-09-15") and label == "기간별 학습 기록(9/15)"
    assert result["count"] == 1 and result["records"][0] == {"date": "2026-09-15", "value": 12, "memo": "굿"}
    _, label2 = chat_tools.run_tool("get_records", {"start": "2026-09-15", "end": "2026-09-22"})
    assert label2 == "기간별 학습 기록(9/15~9/22)"


@pytest.mark.parametrize(
    "args",
    [{}, {"start": "2026-09-15"}, {"start": "9/15", "end": "9/16"}, {"start": "2026-02-30", "end": "2026-03-01"}, {"start": "2026-09-20", "end": "2026-09-10"}],
)
def test_get_records_bad_args_return_error_not_exception(args, monkeypatch):
    monkeypatch.setattr(data_service, "export_items", lambda s, e: pytest.fail("조회하면 안 됨"))
    result, _ = chat_tools.run_tool("get_records", args)
    assert "error" in result


def test_get_records_caps_rows(monkeypatch):
    many = [{"date": f"2026-01-{d:02d}", "value": 1, "memo": ""} for d in range(1, 29)] * 4  # 112개
    monkeypatch.setattr(data_service, "export_items", lambda s, e: many)
    result, _ = chat_tools.run_tool("get_records", {"start": "2026-01-01", "end": "2026-12-31"})
    assert result["count"] == 112 and result["truncated"] and len(result["records"]) == chat_tools.MAX_RECORDS


def test_get_statistics_all_and_range(monkeypatch):
    monkeypatch.setattr(data_service, "export_items", lambda s, e: ROWS)
    r, label = chat_tools.run_tool("get_statistics", {})
    assert label == "학습 통계(전체)"
    assert r["recorded_days"] == 3 and r["max"] == 12 and r["min"] == 4 and r["average"] == 8.3
    assert r["longest_streak"]["days"] == 2 and r["best_weekday"] == "화"  # 9/15 = 화
    assert all(w["count"] for w in r["weekday_average"])
    _, label2 = chat_tools.run_tool("get_statistics", {"start": "2026-09-01", "end": "2026-09-30"})
    assert label2 == "학습 통계(9/1~9/30)"


def test_unknown_tool_and_internal_failure(monkeypatch):
    r, _ = chat_tools.run_tool("drop_everything", {})
    assert "error" in r

    def boom(s, e):
        raise RuntimeError("db down")

    monkeypatch.setattr(data_service, "export_items", boom)
    r, _ = chat_tools.run_tool("get_records", {"start": "2026-09-01", "end": "2026-09-02"})
    assert "error" in r and "RuntimeError" in r["error"]


def test_conversation_tools(monkeypatch):
    from datetime import datetime, timezone

    from app.services import conversation_service as cs

    monkeypatch.setattr(
        cs, "list_items",
        lambda limit: [{"id": "c1", "title": "최근 7일 어땠어?", "created_at": None, "updated_at": datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc), "message_count": 4}],
    )
    r, label = chat_tools.run_tool("list_conversations", {"limit": 999})
    assert label == "지난 대화 목록" and r["conversations"][0]["last_date"] == "2026-10-01"  # UTC 16시 = 한국 다음날 1시

    msgs = [{"role": "user", "content": "가" * 900}] + [{"role": "assistant", "content": "답"}] * 30
    monkeypatch.setattr(cs, "get", lambda cid: {"title": "제목", "message_count": 31, "messages": msgs})
    r, label = chat_tools.run_tool("get_conversation", {"conversation_id": "c1"})
    assert label == "지난 대화 내용(제목)" and len(r["messages"]) == chat_tools.MAX_MESSAGES

    def missing(cid):
        raise cs.ConversationNotFoundError(cid)

    monkeypatch.setattr(cs, "get", missing)
    r, _ = chat_tools.run_tool("get_conversation", {"conversation_id": "nope"})
    assert "error" in r
    assert "error" in chat_tools.run_tool("get_conversation", {})[0]


# ---------- GPT와 도구 주고받기 ----------
def _tool_call(name, args, cid="call_1"):
    return NS(id=cid, function=NS(name=name, arguments=args if isinstance(args, str) else json.dumps(args)))


def _resp(content=None, tool_calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _use(monkeypatch, client):
    monkeypatch.setattr(llm_service, "_client", lambda: client)


def test_tool_round_trip(monkeypatch):
    client = FakeClient([_resp(tool_calls=[_tool_call("get_records", {"start": "2026-09-15", "end": "2026-09-15"})]), _resp("12개 외우셨어요")])
    _use(monkeypatch, client)
    ran = []

    def run(name, args):
        ran.append((name, args))
        return {"count": 1}, "기간별 학습 기록(9/15)"

    text, calls = llm_service.complete_with_tools([{"role": "user", "content": "9/15?"}], chat_tools.TOOLS, run)
    assert text == "12개 외우셨어요" and ran == [("get_records", {"start": "2026-09-15", "end": "2026-09-15"})]
    assert calls == [{"name": "get_records", "arguments": {"start": "2026-09-15", "end": "2026-09-15"}, "label": "기간별 학습 기록(9/15)"}]
    second = client.requests[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "call_1"
    assert second[-1] == {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"count": 1})}
    assert client.requests[0]["tools"] == chat_tools.TOOLS


def test_no_tool_needed_answers_directly(monkeypatch):
    _use(monkeypatch, FakeClient([_resp("요약만으로 답해요")]))
    text, calls = llm_service.complete_with_tools([{"role": "user", "content": "q"}], chat_tools.TOOLS, lambda n, a: pytest.fail("호출하면 안 됨"))
    assert text == "요약만으로 답해요" and calls == []


def test_unsupported_tools_fall_back_to_plain_chat(monkeypatch):
    client = FakeClient([RuntimeError("tools not supported"), _resp("일반 답변")])
    _use(monkeypatch, client)
    text, calls = llm_service.complete_with_tools([{"role": "user", "content": "q"}], chat_tools.TOOLS, lambda n, a: ({}, n))
    assert text == "일반 답변" and calls == [] and "tools" not in client.requests[1]


def test_bad_json_arguments_and_round_limit(monkeypatch):
    # 계속 도구만 부르는 GPT → 마지막 바퀴는 도구 없이 답을 받는다
    endless = [_resp(tool_calls=[_tool_call("get_records", "{not json", f"c{i}")]) for i in range(llm_service.MAX_TOOL_ROUNDS)]
    client = FakeClient([*endless, _resp("결국 답해요")])
    _use(monkeypatch, client)
    text, calls = llm_service.complete_with_tools([{"role": "user", "content": "q"}], chat_tools.TOOLS, lambda n, a: pytest.fail("인자가 깨졌으면 실행하지 않음"))
    assert text == "결국 답해요" and len(calls) == llm_service.MAX_TOOL_ROUNDS
    assert "tools" not in client.requests[-1] and "도구 인자" in client.requests[1]["messages"][-1]["content"]


def test_failure_after_first_round_raises(monkeypatch):
    client = FakeClient([_resp(tool_calls=[_tool_call("list_conversations", {})]), RuntimeError("down")])
    _use(monkeypatch, client)
    with pytest.raises(llm_service.LLMError):
        llm_service.complete_with_tools([{"role": "user", "content": "q"}], chat_tools.TOOLS, lambda n, a: ({}, n))


def test_empty_final_answer_raises(monkeypatch):
    _use(monkeypatch, FakeClient([_resp("  ")]))
    with pytest.raises(llm_service.LLMError):
        llm_service.complete_with_tools([{"role": "user", "content": "q"}], chat_tools.TOOLS, lambda n, a: ({}, n))


# ---------- /api/chat 흐름 ----------
def test_chat_saves_tool_labels_and_strips_them_for_gpt(monkeypatch):
    from app.schemas.chat import ChatRequest
    from app.services import chat_service, conversation_service as cs, summary_service

    summary = {
        "today": "2026-10-06",
        "overall": {"period": {"start": None, "end": None}, "count": 0, "average": None, "max": None, "min": None},
        "recent_7d": {"period": {"start": "2026-09-30", "end": "2026-10-06"}, "count": 0, "average": None, "max": None,
                      "min": None, "previous_average": None, "trend": "비교 불가"},
    }
    monkeypatch.setattr(summary_service, "get_summary", lambda: summary)
    old = [{"role": "user", "content": "이전 질문"}, {"role": "assistant", "content": "이전 답", "tools": ["지난 대화 목록"]}]
    monkeypatch.setattr(cs, "get", lambda cid: {"id": cid, "messages": old})
    sent = {}

    def fake_llm(messages, tools, run):
        sent["messages"] = messages
        sent["tools"] = tools
        return "12개요", [{"name": "get_records", "arguments": {}, "label": "기간별 학습 기록(9/15)"}] * 2  # 같은 조회 두 번

    monkeypatch.setattr(llm_service, "complete_with_tools", fake_llm)
    saved = {}

    def fake_append(cid, msgs):
        saved["msgs"] = msgs
        return {"id": cid, "title": "t"}

    monkeypatch.setattr(cs, "append", fake_append)
    out = chat_service.chat(ChatRequest(conversation_id="c1", message="9/15에 몇 개?"))
    assert out["tools"] == ["기간별 학습 기록(9/15)"] and out["reply"] == "12개요"
    assert saved["msgs"][1] == {"role": "assistant", "content": "12개요", "tools": ["기간별 학습 기록(9/15)"]}
    assert "tools" not in saved["msgs"][0]
    assert all(set(m) == {"role", "content"} for m in sent["messages"])  # GPT에는 role/content 만
    assert sent["tools"] is chat_tools.TOOLS and "조회 도구" in sent["messages"][0]["content"]
