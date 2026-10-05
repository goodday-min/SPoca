// 백엔드 API 클라이언트. 화면 코드는 fetch를 직접 쓰지 않고 이 파일의 함수만 부른다.
import { API_BASE_URL } from "./config.js";
import { trackSlowRequest } from "./ui.js";

const NETWORK_ERROR = "서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요";
const UNKNOWN_ERROR = "요청을 처리하지 못했어요";

/** 서버가 보낸 오류(상태 코드 + 한국어 문구) */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 네트워크 오류면 0
  }
}

async function request(method, path, { body, query } = {}) {
  let url = API_BASE_URL + path;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") params.set(k, v);
    }
    const qs = params.toString();
    if (qs) url += "?" + qs;
  }

  const done = trackSlowRequest(); // 3초 넘게 걸리면 "서버를 깨우는 중" 안내
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    done();
    throw new ApiError(NETWORK_ERROR, 0); // 서버가 꺼져 있거나 인터넷/CORS 문제
  }

  if (res.status === 204) {
    done();
    return null;
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* JSON이 아닌 응답 */
  }
  done();

  if (!res.ok) {
    // 백엔드는 모든 오류를 {"detail": "한국어 문구"} 로 보낸다.
    const message = data && typeof data.detail === "string" ? data.detail : UNKNOWN_ERROR;
    throw new ApiError(message, res.status);
  }
  return data;
}

export const api = {
  get: (path, query) => request("GET", path, { query }),
  post: (path, body) => request("POST", path, { body }),
  put: (path, body) => request("PUT", path, { body }),
  del: (path) => request("DELETE", path),

  // --- 학습 기록 ---
  getSummary: () => request("GET", "/data/summary"),
  listData: (limit = 20, cursor, start, end) =>
    request("GET", "/data", { query: { limit, cursor, start, end } }),
  createData: (item) => request("POST", "/data", { body: item }),
  updateData: (id, item) => request("PUT", `/data/${id}`, { body: item }),
  deleteData: (id) => request("DELETE", `/data/${id}`),

  // --- 대화 ---
  listConversations: (limit = 50) => request("GET", "/conversations", { query: { limit } }),
  getConversation: (id) => request("GET", `/conversations/${id}`),
  deleteConversation: (id) => request("DELETE", `/conversations/${id}`),
  chat: (message, conversationId) =>
    request("POST", "/chat", { body: { message, conversation_id: conversationId || null } }),

  // --- 상태 확인 ---
  health: () => request("GET", "/health"),
};
