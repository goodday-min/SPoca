"""스포카 MCP 서버 (보너스 5.1 B). Claude 같은 바깥 AI 프로그램이 내 학습 기록을 조회할 수 있게 한다.

내 PC에서 stdio 방식으로 실행된다: Claude 앱이 이 프로그램을 직접 켜고 표준 입출력으로 대화한다.
인터넷에 주소를 열지 않으므로 외부에서 접근할 수 없고, 읽기 전용 조회 도구 4개만 제공한다.
(Firestore 키 등은 backend/.env 를 그대로 사용한다)

등록 (Claude Code, 터미널):
    claude mcp add spoca -- <파이썬 경로> <이 파일의 전체 경로>
도구 목록만 확인:
    python mcp_server.py --list

주의: stdio 방식에서는 표준 출력(print)이 통신 채널이다. 이 파일과 도구 코드에서 print 를 쓰면 안 된다.
"""
import asyncio
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x 에서는 FastMCP 가 MCPServer 로 바뀌어 이 코드가 동작하지 않는다
    sys.exit(
        "mcp 패키지가 없거나 버전이 맞지 않아요 (mcp 2.x 는 지원하지 않아요).\n"
        '다음을 실행해 주세요:  pip install -r requirements-mcp.txt   (또는  pip install "mcp>=1.2,<2")'
    )

from app.services import mcp_tools

mcp = FastMCP("spoca")

try:  # 읽기 전용임을 알리는 표시 (지원하는 mcp 버전에서만)
    from mcp.types import ToolAnnotations

    ANNOTATIONS = {"annotations": ToolAnnotations(readOnlyHint=True)}
except Exception:  # pragma: no cover
    ANNOTATIONS = {}

for name, fn in mcp_tools.TOOL_FUNCTIONS.items():
    mcp.add_tool(fn, name=name, description=mcp_tools.DESCRIPTIONS[name], **ANNOTATIONS)


def main() -> None:
    if "--list" in sys.argv:
        for t in asyncio.run(mcp.list_tools()):
            print(f"{t.name}: {t.description}")
        return
    mcp.run()  # 기본 전송 방식: stdio


if __name__ == "__main__":
    main()
