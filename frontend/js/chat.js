// AI코치 화면: 요약 한 줄, 대화, 예시 질문, 지난 대화 패널
import { api } from "./api.js";
import { showToast, WAKING_MESSAGE } from "./ui.js";

const SLOW_AFTER_MS = 3000; // 답변이 이 시간보다 늦으면 "서버를 깨우는 중" 줄을 보여 준다

const $ = (id) => document.getElementById(id);

const state = {
  conversationId: null, // null이면 새 대화
  waiting: false,
};

// ---------- 요약 한 줄 ----------
const TREND_MARK = { 증가: " ↑", 감소: " ↓", 유지: " →", "비교 불가": "" };

async function loadStrip() {
  try {
    const s = await api.getSummary();
    const o = s.overall;
    $("strip-overall").textContent =
      o.count === 0 ? "아직 기록이 없어요" : `전체 ${o.count}일 · 평균 ${o.average}`;
    const t = s.recent_7d.trend;
    $("strip-recent").textContent = `최근 7일 ${t}${TREND_MARK[t] ?? ""}`;
  } catch {
    $("strip-overall").textContent = "요약을 불러오지 못했어요";
    $("strip-recent").textContent = "";
  }
}

// ---------- 말풍선 ----------
function botIcon() {
  const ava = document.createElement("div");
  ava.className = "ava";
  ava.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 14h.01M15 14h.01"/></svg>';
  return ava;
}

function addMessage(role, text) {
  const list = $("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (role === "user" ? " me" : "");
  bubble.textContent = text; // 줄바꿈은 CSS(pre-wrap)로 보여 준다
  if (role === "user") {
    list.appendChild(bubble);
  } else {
    const row = document.createElement("div");
    row.className = "msg-row";
    row.append(botIcon(), bubble);
    list.appendChild(row);
  }
  scrollToBottom();
  return bubble;
}

function addWaitingBubble() {
  const row = document.createElement("div");
  row.className = "msg-row";
  const bubble = document.createElement("div");
  bubble.className = "bubble wait";
  const line = document.createElement("div");
  line.textContent = "답변을 만드는 중…";
  const sub = document.createElement("div");
  sub.className = "wait-sub";
  sub.textContent = WAKING_MESSAGE;
  sub.hidden = true;
  bubble.append(line, sub);
  row.append(botIcon(), bubble);
  $("chat-messages").appendChild(row);
  scrollToBottom();
  const timer = setTimeout(() => {
    sub.hidden = false;
    scrollToBottom();
  }, SLOW_AFTER_MS);
  return { row, stop: () => clearTimeout(timer) };
}

function scrollToBottom() {
  const body = $("chat-body");
  body.scrollTop = body.scrollHeight;
}

// 답변이 끝날 때마다 예시 질문을 대화 맨 아래에 다시 보여 준다 (처음 화면의 것과 같은 질문)
function removeSuggestions() {
  document.getElementById("chat-suggest")?.remove();
}

function showSuggestions() {
  removeSuggestions();
  const box = document.createElement("div");
  box.id = "chat-suggest";
  const note = document.createElement("p");
  note.className = "faint-note";
  note.textContent = "이런 걸 물어볼 수 있어요";
  const chips = document.createElement("div");
  chips.className = "chips";
  document.querySelectorAll("#chat-welcome .chip").forEach((src) => {
    const c = document.createElement("button");
    c.type = "button";
    c.className = "chip";
    c.dataset.q = src.dataset.q;
    c.textContent = src.textContent;
    c.addEventListener("click", () => send(c.dataset.q));
    chips.appendChild(c);
  });
  box.append(note, chips);
  $("chat-messages").appendChild(box);
  scrollToBottom();
}

function showWelcome(show) {
  $("chat-welcome").hidden = !show;
}

function setWaiting(on) {
  state.waiting = on;
  $("chat-send").disabled = on;
  $("chat-input").disabled = on;
  $("chat-new").disabled = on;
  $("chat-history").disabled = on;
  document.querySelectorAll("#chat-welcome .chip, #chat-suggest .chip").forEach((c) => (c.disabled = on));
}

// ---------- 보내기 ----------
async function send(text) {
  text = text.trim();
  if (!text || state.waiting) return;

  showWelcome(false);
  removeSuggestions();
  const userBubble = addMessage("user", text);
  $("chat-input").value = "";
  setWaiting(true);
  const wait = addWaitingBubble();
  try {
    const res = await api.chat(text, state.conversationId);
    state.conversationId = res.conversation_id; // 다음 질문이 이어지도록 기억
    wait.stop();
    wait.row.remove();
    addMessage("assistant", res.reply);
    showSuggestions();
  } catch (e) {
    // 서버에 저장되지 않았으므로 화면에서도 질문을 지우고, 입력창에 되돌려 놓는다
    wait.stop();
    wait.row.remove();
    userBubble.remove();
    $("chat-input").value = text;
    if (!$("chat-messages").children.length) showWelcome(true);
    else showSuggestions(); // 앞선 답변이 있었다면 예시 질문을 다시 보여 준다
    showToast(e.message, { isError: true });
  } finally {
    setWaiting(false);
    $("chat-input").focus();
  }
}

// ---------- 새 대화 / 불러오기 ----------
function resetConversation() {
  state.conversationId = null;
  $("chat-messages").replaceChildren(); // 예시 질문 블록도 함께 사라진다
  showWelcome(true);
  $("chat-input").value = "";
}

async function openConversation(id) {
  try {
    const conv = await api.getConversation(id);
    state.conversationId = conv.id;
    $("chat-messages").replaceChildren();
    showWelcome(false);
    conv.messages.forEach((m) => addMessage(m.role, m.content));
    $("chat-sheet").close();
    scrollToBottom();
  } catch (e) {
    showToast(e.message, { isError: true });
  }
}

// ---------- 지난 대화 패널 ----------
const TRASH = "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3";

function kstDate(iso) {
  return new Date(iso).toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" }); // YYYY-MM-DD
}

function dateLabel(iso) {
  const day = kstDate(iso);
  const today = kstDate(new Date().toISOString());
  const yesterday = kstDate(new Date(Date.now() - 86400000).toISOString());
  if (day === today) return "오늘";
  if (day === yesterday) return "어제";
  const [, m, d] = day.split("-");
  return `${Number(m)}월 ${Number(d)}일`;
}

function renderSheet(items) {
  const list = $("chat-sheet-list");
  list.replaceChildren();
  const state_ = $("chat-sheet-state");
  state_.hidden = items.length > 0;
  if (!items.length) state_.textContent = "지난 대화가 없어요";

  for (const c of items) {
    const row = document.createElement("div");
    row.className = "sheet-row";

    const main = document.createElement("button");
    main.type = "button";
    main.className = "sheet-main";
    const title = document.createElement("b");
    title.textContent = c.title;
    const meta = document.createElement("span");
    meta.className = "muted";
    meta.textContent = `${dateLabel(c.updated_at)} · ${c.message_count}개 메시지`;
    main.append(title, meta);
    main.addEventListener("click", () => openConversation(c.id));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "icon-btn";
    del.setAttribute("aria-label", "삭제");
    del.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${TRASH}"/></svg>`;
    del.addEventListener("click", () => removeConversation(c, del));

    row.append(main, del);
    list.appendChild(row);
  }
}

async function loadSheet() {
  const msg = $("chat-sheet-state");
  msg.hidden = false;
  msg.textContent = "불러오는 중…";
  try {
    renderSheet(await api.listConversations(50));
  } catch (e) {
    $("chat-sheet-list").replaceChildren();
    msg.hidden = false;
    msg.textContent = e.message;
  }
}

async function removeConversation(c, btn) {
  btn.disabled = true;
  try {
    await api.deleteConversation(c.id); // 확인 없이 바로 삭제
    if (c.id === state.conversationId) resetConversation(); // 보던 대화를 지우면 새 대화로
    await loadSheet();
  } catch (e) {
    btn.disabled = false;
    showToast(e.message, { isError: true });
  }
}

// ---------- 연결 ----------
export function init() {
  $("chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    send($("chat-input").value);
  });
  document.querySelectorAll("#chat-welcome .chip").forEach((c) =>
    c.addEventListener("click", () => send(c.dataset.q))
  );
  $("chat-new").addEventListener("click", resetConversation);
  $("chat-history").addEventListener("click", () => {
    $("chat-sheet").showModal();
    loadSheet();
  });
  $("chat-sheet-close").addEventListener("click", () => $("chat-sheet").close());
  // 패널 바깥(어두운 배경)을 누르면 닫는다
  $("chat-sheet").addEventListener("click", (e) => {
    if (e.target === $("chat-sheet")) $("chat-sheet").close();
  });
}

/** 이 화면이 보일 때마다 맨 위 요약을 최신으로, 대화는 새 대화로 시작 (이전 대화는 "지난 대화"에서) */
export function show() {
  if (!state.waiting) resetConversation(); // 답변을 기다리는 중에 다녀온 경우만 그대로 둔다
  loadStrip();
}
