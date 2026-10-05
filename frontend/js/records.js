// 학습 기록 화면: 요약 카드, 기록 목록(더 보기), 추가·수정 팝업, 삭제
import { api } from "./api.js";
import { showToast, withLoading } from "./ui.js";

const PAGE_SIZE = 20; // 처음과 "더 보기"마다 불러오는 개수
const MAX_LIMIT = 100; // 서버가 한 번에 주는 최대 개수

const $ = (id) => document.getElementById(id);

const state = {
  items: [],
  nextCursor: null,
  summary: null,
  range: "overall", // "overall" | "recent_7d"
  editingId: null, // null이면 추가, 아니면 수정 중인 기록 id
};

// ---------- 공통 ----------
function todayKst() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" }); // YYYY-MM-DD
}

function icon(pathD) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  svg.appendChild(path);
  return svg;
}

function iconButton(label, pathD, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon-btn";
  b.setAttribute("aria-label", label);
  b.appendChild(icon(pathD));
  b.addEventListener("click", () => onClick(b));
  return b;
}

const EDIT_ICON = "M4 20l1-4L16 5l3 3L8 19zM14 7l3 3";
const DELETE_ICON = "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3";

// ---------- 요약 카드 ----------
const dash = (v) => (v === null || v === undefined ? "-" : String(v));

function renderSummary() {
  const err = $("rec-summary-error");
  if (!state.summary) return;
  err.hidden = true;
  const s = state.summary[state.range];
  const { start, end } = s.period;
  $("rec-period").textContent = start ? `기간 ${start} ~ ${end}` : "기간 기록 없음";
  $("rec-count").textContent = s.count;
  $("rec-avg").textContent = dash(s.average);
  $("rec-max").textContent = dash(s.max);
  $("rec-min").textContent = dash(s.min);
  // 추세는 최근 7일 기준이라 두 보기에서 같은 값을 보여 준다
  $("rec-trend").textContent = state.summary.recent_7d.trend;
  document.querySelectorAll("#rec-summary .seg-btn").forEach((b) => {
    const on = b.dataset.range === state.range;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
}

async function loadSummary() {
  try {
    state.summary = await api.getSummary();
    renderSummary();
  } catch (e) {
    const err = $("rec-summary-error");
    err.textContent = e.message;
    err.hidden = false;
  }
}

// ---------- 목록 ----------
function renderList() {
  const list = $("rec-list");
  list.replaceChildren();
  for (const item of state.items) {
    const row = document.createElement("div");
    row.className = "rec-row";

    const text = document.createElement("div");
    text.className = "rec-text";
    const date = document.createElement("b");
    date.textContent = item.date;
    const detail = document.createElement("span");
    detail.className = "muted";
    detail.textContent = `외운 단어 ${item.value}개` + (item.memo ? ` · ${item.memo}` : "");
    text.append(date, detail);

    row.append(
      text,
      iconButton("수정", EDIT_ICON, () => openDialog(item)),
      iconButton("삭제", DELETE_ICON, (btn) => removeItem(item, btn))
    );
    list.appendChild(row);
  }
  $("rec-more").hidden = !state.nextCursor;
  const msg = $("rec-state");
  msg.hidden = state.items.length > 0;
  if (!state.items.length) msg.textContent = state.range === "recent_7d" ? "최근 7일 기록이 없어요" : "아직 기록이 없어요";
  list.hidden = state.items.length === 0;
}

function showListError(message) {
  const msg = $("rec-state");
  msg.hidden = false;
  msg.textContent = message;
}

/** 목록에 걸 기간. "최근 7일" 탭이면 요약 카드와 같은 기간, "전체"면 제한 없음 */
function listRange() {
  if (state.range === "recent_7d" && state.summary) {
    const { start, end } = state.summary.recent_7d.period;
    return { start, end };
  }
  return {};
}

/** 처음부터 limit개를 다시 불러온다. */
async function reloadList(limit = PAGE_SIZE) {
  const msg = $("rec-state");
  if (!state.items.length) {
    msg.hidden = false;
    msg.textContent = "불러오는 중…";
  }
  try {
    const { start, end } = listRange();
    const res = await api.listData(Math.min(Math.max(limit, PAGE_SIZE), MAX_LIMIT), undefined, start, end);
    state.items = res.items;
    state.nextCursor = res.next_cursor;
    renderList();
  } catch (e) {
    state.items = [];
    state.nextCursor = null;
    renderList();
    showListError(e.message);
  }
}

async function loadMore() {
  const { start, end } = listRange();
  const res = await api.listData(PAGE_SIZE, state.nextCursor, start, end);
  state.items = state.items.concat(res.items);
  state.nextCursor = res.next_cursor;
  renderList();
}

/** 추가·수정·삭제 뒤: 지금 보이던 만큼 다시 불러오고 요약도 갱신 */
async function refreshAll() {
  await Promise.all([reloadList(state.items.length), loadSummary()]);
}

async function removeItem(item, btn) {
  await withLoading(btn, async () => {
    await api.deleteData(item.id); // 확인 없이 바로 삭제
    await refreshAll();
  });
}

// ---------- 추가·수정 팝업 ----------
function openDialog(item = null) {
  state.editingId = item ? item.id : null;
  $("rec-dialog-title").textContent = item ? "기록 수정" : "기록 추가";
  $("rec-date").value = item ? item.date : todayKst();
  $("rec-value").value = item ? item.value : "";
  $("rec-memo").value = item ? item.memo : "";
  hideDialogError();
  $("rec-dialog").showModal();
}

function showDialogError(message) {
  const tip = $("rec-error");
  tip.textContent = message;
  tip.hidden = false;
}
function hideDialogError() {
  $("rec-error").hidden = true;
}

async function submitDialog(event) {
  event.preventDefault();
  hideDialogError();

  const date = $("rec-date").value;
  const rawValue = $("rec-value").value.trim();
  if (!date) return showDialogError("날짜를 선택해 주세요");
  if (rawValue === "") return showDialogError("외운 단어 수를 입력해 주세요");
  const value = Number(rawValue);
  if (!Number.isInteger(value) || value < 0) return showDialogError("외운 단어 수는 0 이상의 정수여야 해요");

  const payload = { date, value, memo: $("rec-memo").value.trim() };
  const btn = $("rec-save");
  btn.disabled = true;
  try {
    if (state.editingId) await api.updateData(state.editingId, payload);
    else await api.createData(payload);
    $("rec-dialog").close();
    await refreshAll();
    showToast(state.editingId ? "기록을 수정했어요" : "기록을 추가했어요");
  } catch (e) {
    showDialogError(e.message); // 예: 이미 기록이 있어요
  } finally {
    btn.disabled = false;
  }
}

// ---------- 연결 ----------
export function init() {
  $("rec-add").addEventListener("click", () => openDialog());
  $("rec-cancel").addEventListener("click", () => $("rec-dialog").close());
  $("rec-form").addEventListener("submit", submitDialog);
  $("rec-more").addEventListener("click", (e) => withLoading(e.currentTarget, loadMore));
  document.querySelectorAll("#rec-summary .seg-btn").forEach((b) =>
    b.addEventListener("click", async () => {
      state.range = b.dataset.range;
      if (!state.summary) await loadSummary(); // 기간을 알아야 목록을 거를 수 있다
      renderSummary();
      reloadList(PAGE_SIZE);
    })
  );
}

/** 이 화면이 보일 때마다 최신 상태로 불러온다 */
export function show() {
  reloadList(PAGE_SIZE);
  loadSummary();
}
