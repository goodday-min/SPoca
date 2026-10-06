"""MCP 서버(mcp_server.py)가 바깥 AI 프로그램(Claude 등)에 열어 주는 도구 함수.

AI코치의 Function Calling(chat_tools.py)과 같은 조회 함수를 그대로 쓴다. 이 파일은 'MCP 규격'을
모르는 평범한 함수만 담아서, MCP 패키지 없이도 시험할 수 있다. (등록은 mcp_server.py)
조회만 하는 읽기 전용 도구이고, 오류는 예외 대신 {"error": ...} 로 돌려준다.
"""
from app.services import chat_tools

# 도구 설명은 chat_tools.TOOLS 한 곳에서만 관리한다 (AI코치와 MCP가 같은 설명을 쓴다)
DESCRIPTIONS = {t["function"]["name"]: t["function"]["description"] for t in chat_tools.TOOLS}


def get_records(start: str, end: str) -> dict:
    """기간 안의 날짜별 학습 기록. start, end 는 YYYY-MM-DD (하루만 보려면 같게)."""
    return chat_tools.run_tool("get_records", {"start": start, "end": end})[0]


def get_statistics(start: str | None = None, end: str | None = None) -> dict:
    """기간의 통계·최장 연속 기록·요일별 평균. 기간을 비우면 전체."""
    args = {k: v for k, v in (("start", start), ("end", end)) if v}
    return chat_tools.run_tool("get_statistics", args)[0]


def list_conversations(limit: int = 10) -> dict:
    """지난 AI코치 대화 목록 (최근순, 1~20개)."""
    return chat_tools.run_tool("list_conversations", {"limit": limit})[0]


def get_conversation(conversation_id: str) -> dict:
    """지난 대화 한 개의 최근 메시지."""
    return chat_tools.run_tool("get_conversation", {"conversation_id": conversation_id})[0]


TOOL_FUNCTIONS = {
    "get_records": get_records,
    "get_statistics": get_statistics,
    "list_conversations": list_conversations,
    "get_conversation": get_conversation,
}
