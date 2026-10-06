# 스포카 (Spoca) — 나만의 AI 비서

내 학습 기록(일별 외운 단어 수)을 분석해 Firestore에 저장하고, AI가 그 요약을 바탕으로 코칭해 주는 웹 서비스입니다.

> 작성 중입니다. 서비스 소개, 배포 URL, 실행 방법, 환경변수 목록, 시드 실행 방법, 스크린샷은 M6 단계에서 채웁니다.

## 폴더 구조
```
backend/    FastAPI 서버 (app/routers, services, schemas, core), MCP 서버(mcp_server.py)
frontend/   바닐라 HTML/CSS/JS
scripts/    시드 스크립트, 시험·진단 스크립트
docs/       README에 쓰는 그림 (docs/images)
```

## 기획 문서
시나리오, 요구사항 명세서(PRD), 화면 설계서, 작업지시서(TASK)는 claude.ai 프로젝트 "M1_2 AI Agent 개발(스포카)"에 있습니다.

## 보너스 5.1 — GPT 도구 호출(Function Calling)과 MCP 서버

AI코치가 **요약에 없는 내용**(예: "지난달 15일에 몇 개 외웠어?")을 물어도 답할 수 있도록, 같은 조회 함수 4개를 **두 가지 방법**으로 연결했습니다.

| 도구(함수) | 하는 일 |
| --- | --- |
| `get_records` | 기간의 날짜별 학습 기록 조회 |
| `get_statistics` | 기간 통계, 최장 연속 기록, 요일별 평균 |
| `list_conversations` | 지난 AI코치 대화 목록 |
| `get_conversation` | 지난 대화 한 개의 내용 |

모두 **읽기 전용**이고, 코드는 한 곳(`backend/app/services/chat_tools.py`)에서 관리합니다.

![Function Calling과 MCP 비교](docs/images/function-calling-vs-mcp.png)

### A. Function Calling (앱 안에서 동작)
- 서버(`/api/chat`)가 질문과 **학습 기록 요약**, 그리고 **도구 설명서(스키마)** 를 GPT에 함께 보냅니다. 요약 주입은 그대로 유지됩니다.
- GPT가 요약만으로 부족하다고 판단하면 "`get_records`를 이 날짜로 실행해 주세요"라고 요청하고, **서버가 해당 함수를 대신 실행**해 결과를 돌려줍니다. 한 질문에 최대 3번까지 연달아 부를 수 있습니다.
- 교육장 서버가 도구 호출을 지원하지 않으면 자동으로 요약만으로 답합니다.
- **호출 기록 확인**: AI코치 답변 아래에 "조회한 것: 기간별 학습 기록(9/15) · …"이 표시되고(대화에도 저장), 서버 터미널에도 도구 이름과 인자가 남습니다.
- 코드: `app/services/chat_tools.py`(도구·스키마·실행), `app/services/llm_service.py`(`complete_with_tools`), `app/services/chat_service.py`
- 시험: 서버를 켠 뒤 `python scripts/chat_tools_demo.py`

### B. MCP 서버 (앱 밖의 Claude가 호출)
같은 함수를 **MCP 규격**으로 열어, 우리 앱 밖의 Claude(Claude Code)가 내 학습 기록을 조회할 수 있게 했습니다.
내 PC에서 **stdio 방식**으로 실행되며(Claude가 직접 켬), 인터넷에 주소를 열지 않아 외부에서 접근할 수 없습니다.

![MCP 서버 개요와 테스트 순서](docs/images/mcp-overview.png)

```powershell
# 1) 설치 (backend 폴더, 가상환경을 켠 상태). mcp 2.x 는 지원하지 않아 <2 로 고정되어 있습니다
pip install -r requirements-mcp.txt

# 2) 도구 4개가 등록되는지 확인
python mcp_server.py --list

# 3) 가상환경의 파이썬 경로 확인
python -c "import sys; print(sys.executable)"

# 4) Claude Code 에 등록 (경로는 내 PC에 맞게)
claude mcp add spoca -- <3번의 파이썬 경로> C:\Users\user\codyssey\M1_2_SPoca2\backend\mcp_server.py

# 5) claude 실행 후 질문: "spoca로 2026-09-15 학습 기록 조회해 줘"  (도구 호출 허용 → 결과 확인, /mcp 로 연결 상태 확인)
```

- 코드: `backend/mcp_server.py`(등록·실행), `backend/app/services/mcp_tools.py`(MCP용 함수, `chat_tools`를 그대로 호출)
- 배포(Render)에는 필요 없어서 `requirements.txt`가 아닌 `requirements-mcp.txt`로 분리했습니다.

### A와 B의 차이
- 누가 부르는가: A는 **앱 안의 GPT**, B는 **앱 밖의 Claude**.
- 도구를 알려 주는 방식: A는 **요청마다 스키마를 GPT에 직접 전달**, B는 AI 프로그램이 MCP로 **목록을 물어봄**.
- 실제로 데이터를 읽는 함수 4개는 **같은 코드**입니다.

### 호출 근거와 흐름 (어떤 근거로 어떤 도구를 불렀나)

**근거**: 도구를 고르는 것은 GPT(A) 또는 Claude(B)이고, 판단 재료는 두 가지입니다.
1. **도구 설명서(스키마)** — 각 도구의 이름·설명·인자(`chat_tools.py`의 `TOOLS`). B에서는 같은 설명이 MCP 도구 목록으로 전달됩니다.
2. **질문 내용과 이미 가진 정보** — 학습 기록 요약(최근 7일·전체)에 답이 있으면 부르지 않고, 없을 때만 부릅니다.

| 질문 유형 | 부르는 도구 | 근거 |
| --- | --- | --- |
| "9월 15일에 몇 개 외웠어?" (특정 날짜·기간) | `get_records` | 요약에는 최근 7일 합계만 있어 날짜별 값이 필요함 |
| "최장 연속 기록이랑 잘한 요일은?" | `get_statistics` | 연속 일수·요일별 평균은 요약에 없고 통계 도구가 계산함 |
| "지난번에 무슨 얘기했지?" | `list_conversations` | 먼저 대화 목록에서 찾을 대화를 고름 |
| "그 대화 내용 다시 알려줘" | `get_conversation` | 목록에서 고른 대화의 메시지를 읽음 |
| "최근 7일 평균은?" | 없음 | 요약에 이미 있어 도구 없이 답함 |

**흐름 A — 앱 안의 GPT (`/api/chat`)**
```
사용자 질문
  → 서버: 요약 + 도구 설명서를 GPT에 전달
  → GPT: 요약으로 충분하면 바로 답 / 부족하면 "get_records(날짜=…) 실행해 주세요" 요청
  → 서버: 해당 함수를 실행(읽기 전용)하고 결과를 GPT에 전달   ← 최대 3번 반복
  → GPT: 결과를 반영해 최종 답변
  → 서버: 답변 + 부른 도구 이름을 대화에 저장 → 화면에 "조회한 것: …" 표시
```
확인 방법: 화면의 "조회한 것" 표시, 서버 로그(도구 이름·인자), `python scripts/chat_tools_demo.py`.

**흐름 B — 앱 밖의 Claude (MCP)**
```
사용자 질문(Claude Code)
  → Claude: MCP로 spoca 도구 목록을 받아 질문에 맞는 도구 선택
  → 사용자: 도구 호출 허용
  → spoca MCP 서버(내 PC): 같은 함수를 실행해 결과 반환
  → Claude: 결과를 읽어 답변
```

**실제 검증 (B, Claude Code)**
| 질문 | 호출된 도구 | 결과 |
| --- | --- | --- |
| "spoca MCP로 2026-09-15 학습 기록 조회해 줘" | `get_records` | 2026-09-15 · 8개 · 메모 없음 (앱 화면과 일치) |
| "spoca로 내 최장 연속 기록이랑 가장 잘한 요일 알려 줘" | `get_statistics` | 최장 연속 28일(2026-06-22~07-19), 가장 잘한 요일 월요일(평균 8.1) (앱 리포트와 일치) |

**안전 장치**: 도구 결과는 "데이터"로만 쓰고 지시문으로 따르지 않습니다(프롬프트 주입 방지). 모든 도구는 읽기 전용이며, 결과 크기는 제한됩니다(기록 100건, 대화 20개, 메시지 20개 등).

**C. GPT Actions는 구현하지 않았습니다.** ChatGPT "GPT 만들기"는 유료 플랜이 필요해 선택 과제인 C는 제외하고 A→B까지 진행했습니다.
