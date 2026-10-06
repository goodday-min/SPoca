"""MCP 도구 함수 단위 테스트 (mcp 패키지·Firestore 없이)"""
import inspect

from app.services import chat_tools, data_service, mcp_tools

ROWS = [{"date": "2026-09-15", "value": 8, "memo": ""}, {"date": "2026-09-16", "value": 3, "memo": ""}]


def test_every_ai_coach_tool_has_an_mcp_function_with_same_parameters():
    assert set(mcp_tools.TOOL_FUNCTIONS) == {t["function"]["name"] for t in chat_tools.TOOLS}
    for t in chat_tools.TOOLS:
        name = t["function"]["name"]
        params = set(inspect.signature(mcp_tools.TOOL_FUNCTIONS[name]).parameters)
        assert params == set(t["function"]["parameters"]["properties"]), name
        required = set(t["function"]["parameters"].get("required", []))
        needs = {p for p, v in inspect.signature(mcp_tools.TOOL_FUNCTIONS[name]).parameters.items() if v.default is inspect.Parameter.empty}
        assert needs == required, name
        assert mcp_tools.DESCRIPTIONS[name] == t["function"]["description"]


def test_get_records_returns_plain_dict(monkeypatch):
    monkeypatch.setattr(data_service, "export_items", lambda s, e: ROWS)
    out = mcp_tools.get_records("2026-09-15", "2026-09-16")
    assert out["count"] == 2 and out["records"][0]["value"] == 8


def test_statistics_without_dates_means_all(monkeypatch):
    seen = {}

    def fake(s, e):
        seen["r"] = (s, e)
        return ROWS

    monkeypatch.setattr(data_service, "export_items", fake)
    out = mcp_tools.get_statistics()
    assert seen["r"] == (None, None) and out["recorded_days"] == 2 and out["max"] == 8


def test_bad_input_returns_error_dict_not_exception():
    assert "error" in mcp_tools.get_records("9/15", "9/16")
    assert "error" in mcp_tools.get_conversation("")
