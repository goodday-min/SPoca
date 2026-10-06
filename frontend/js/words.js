// 단어장 목록 화면: 정렬, 단계 배지, 수정 팝업, 삭제, "방금 등록" 표시
import { api } from "./api.js";
import { showToast, withLoading, speak, STAGE_LABEL } from "./ui.js";

const $ = (id) => document.getElementById(id);

const state = {
  items: [],
  sort: "latest", // "latest"(최신순) | "stage"(단계순)
  stage: null, // 단계 칩: null이면 전체, 아니면 "New"|"V1"|"V2"|"V3"|"Master" 하나
  query: "", // 검색어 (영어 단어·뜻)
  openRow: null, // 밀어서 삭제 버튼이 열려 있는 줄
  editingId: null,
  justAdded: new Set(), // 이번에 처음 열 때 "방금 등록"을 붙일 단어 id
};

const SPEAKER_ICON = "M4 10v4h4l5 4V6L8 10zM16.5 9a4 4 0 0 1 0 6M19 6.5a7.5 7.5 0 0 1 0 11";
const DELETE_ICON = "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3";
const STAGES = ["New", "V1", "V2", "V3", "Master"];
const DELETE_W = 84; // 밀었을 때 드러나는 삭제 버튼 너비(px)

// ---------- "방금 등록" (영어 대화가 끝난 직후, 단어장을 처음 열 때만 보인다) ----------
const JUST_ADDED_KEY = "spoca.justAdded";

/** 영어 대화에서 방금 등록된 단어 id를 기억해 둔다 (M4에서 사용) */
export function markJustAdded(ids) {
  try {
    sessionStorage.setItem(JUST_ADDED_KEY, JSON.stringify(ids));
  } catch {
    /* 저장이 막힌 환경이면 표시만 생략한다 */
  }
}

/** 기억해 둔 id를 꺼내고 지운다 → 다음에 열 때는 표시가 없다 */
function takeJustAdded() {
  try {
    const raw = sessionStorage.getItem(JUST_ADDED_KEY);
    sessionStorage.removeItem(JUST_ADDED_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

// ---------- 공통 ----------
function icon(pathD) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  svg.appendChild(path);
  return svg;
}

/** 단계 배지 글자와 색. 복습 중이면 단계 이름, 끝난 단어는 외움/못 외움 */
function badgeOf(item) {
  if (item.status === "passed") return { text: "외움", cls: "badge-passed" };
  if (item.status === "failed") return { text: "못 외움", cls: "badge-failed" };
  return { text: STAGE_LABEL[item.stage], cls: item.stage === "Master" ? "badge-master" : item.stage === "New" ? "badge-new" : "badge-step" };
}

const STATUS_LABEL = { reviewing: "복습 중", passed: "외움", failed: "못 외움" };

// ---------- 목록 ----------
function visibleItems() {
  const q = state.query.trim().toLowerCase();
  return state.items.filter((it) => {
    if (state.stage && !(it.status === "reviewing" && it.stage === state.stage)) return false;
    if (q && !(it.word.toLowerCase().includes(q) || (it.meaning || "").toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderChips() {
  const box = $("word-chips");
  box.replaceChildren();
  for (const stage of STAGES) {
    const count = state.items.filter((it) => it.status === "reviewing" && it.stage === stage).length;
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip stage-chip" + (state.stage === stage ? " on" : "");
    chip.setAttribute("aria-pressed", String(state.stage === stage));
    chip.dataset.stage = stage;
    chip.textContent = `${stage === "Master" ? "M" : STAGE_LABEL[stage]} ${count}`;
    chip.addEventListener("click", () => {
      state.stage = state.stage === stage ? null : stage; // 다시 누르면 전체
      renderList();
    });
    box.appendChild(chip);
  }
}

function closeOpenRow() {
  if (state.openRow) setOffset(state.openRow, 0, true);
  state.openRow = null;
}

function setOffset(row, x, animate) {
  row.style.transition = animate ? "transform .18s ease" : "none";
  row.style.transform = x ? `translateX(${x}px)` : "";
  row.dataset.open = x <= -DELETE_W + 1 ? "1" : "";
}

/** 한 줄: 발음 아이콘 + 단어 + 배지. 누르면 수정, 왼쪽으로 밀면 삭제 */
function makeRow(item) {
  const wrap = document.createElement("div");
  wrap.className = "swipe";

  const del = document.createElement("button");
  del.type = "button";
  del.className = "swipe-del";
  del.setAttribute("aria-label", `${item.word} 삭제`);
  del.append(icon(DELETE_ICON), document.createTextNode("삭제"));
  del.addEventListener("click", () => removeItem(item, del));

  const row = document.createElement("div");
  row.className = "word-row";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("aria-label", `${item.word} 수정`);

  const sp = document.createElement("button");
  sp.type = "button";
  sp.className = "speak-btn";
  sp.setAttribute("aria-label", `${item.word} 발음 듣기`);
  sp.appendChild(icon(SPEAKER_ICON));
  sp.addEventListener("click", (e) => {
    e.stopPropagation(); // 발음 듣기는 수정 팝업을 열지 않는다
    speak(item.word);
  });

  const word = document.createElement("b");
  word.className = "word-name";
  word.textContent = item.word;

  const badge = document.createElement("span");
  const b = badgeOf(item);
  badge.className = `badge ${b.cls}`;
  badge.textContent = b.text;

  row.append(sp, word);
  if (state.justAdded.has(item.id)) {
    const tag = document.createElement("span");
    tag.className = "badge badge-just";
    tag.textContent = "방금 등록";
    row.appendChild(tag);
  }
  row.appendChild(badge);

  // 밀기(터치·마우스 모두)와 누르기 구분
  let startX = 0;
  let baseX = 0;
  let dragging = false;
  let moved = false;
  row.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".speak-btn")) return;
    startX = e.clientX;
    baseX = row.dataset.open ? -DELETE_W : 0;
    dragging = true;
    moved = false;
  });
  row.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    if (!moved && Math.abs(dx) < 6) return;
    if (!moved) {
      moved = true;
      if (state.openRow && state.openRow !== row) closeOpenRow();
      row.setPointerCapture?.(e.pointerId);
    }
    setOffset(row, Math.max(-DELETE_W, Math.min(0, baseX + dx)), false);
  });
  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    if (!moved) return;
    const x = parseFloat((row.style.transform.match(/-?[\d.]+/) || ["0"])[0]);
    const open = x < -DELETE_W / 2;
    setOffset(row, open ? -DELETE_W : 0, true);
    state.openRow = open ? row : null;
    row.dataset.justDragged = "1";
    setTimeout(() => delete row.dataset.justDragged, 0); // 끝난 직후의 click은 무시
  };
  row.addEventListener("pointerup", endDrag);
  row.addEventListener("pointercancel", endDrag);
  row.addEventListener("click", () => {
    if (row.dataset.justDragged) return;
    if (row.dataset.open) return closeOpenRow(); // 열려 있으면 눌러서 닫기만
    if (state.openRow) closeOpenRow();
    openDialog(item);
  });
  row.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openDialog(item);
    }
  });

  wrap.append(del, row);
  return wrap;
}

function renderList() {
  state.openRow = null;
  const list = $("word-list");
  list.replaceChildren();
  renderChips();
  const shown = visibleItems();
  for (const item of shown) list.appendChild(makeRow(item));

  const filtered = state.stage !== null || state.query.trim() !== "";
  $("word-total").textContent = `${state.items.length}개`;
  $("word-count").textContent = filtered
    ? `단어 ${shown.length}개 · 전체 ${state.items.length}개`
    : `단어 ${state.items.length}개`;
  const msg = $("word-state");
  msg.hidden = shown.length > 0;
  if (!state.items.length) msg.textContent = "아직 단어가 없어요. 오른쪽 아래 + 버튼으로 시작해 보세요";
  else if (!shown.length) msg.textContent = "찾는 단어가 없어요";
  list.hidden = shown.length === 0;
  $("word-sort").value = state.sort;
}

async function reload() {
  const msg = $("word-state");
  if (!state.items.length) {
    msg.hidden = false;
    msg.textContent = "불러오는 중…";
  }
  try {
    const res = await api.listWords(state.sort);
    state.items = res.items;
    renderList();
  } catch (e) {
    state.items = [];
    renderList();
    msg.hidden = false;
    msg.textContent = e.message;
  }
}

async function removeItem(item, btn) {
  await withLoading(btn, async () => {
    await api.deleteWord(item.id); // 확인 없이 바로 삭제
    await reload();
  });
}

// ---------- 수정 팝업 (단어·뜻·예문만. 단계·상태·등록일은 읽기만) ----------
function showDialogError(message) {
  const tip = $("wd-error");
  tip.textContent = message;
  tip.hidden = false;
}

function openDialog(item) {
  state.editingId = item.id;
  $("wd-word").value = item.word;
  $("wd-meaning").value = item.meaning;
  $("wd-example").value = item.example;
  $("word-info").textContent = `등록일 ${item.registered_date} · ${STAGE_LABEL[item.stage]} 단계 · ${STATUS_LABEL[item.status]}`;
  $("wd-error").hidden = true;
  $("word-dialog").showModal();
}

async function submitDialog(event) {
  event.preventDefault();
  $("wd-error").hidden = true;
  const word = $("wd-word").value.trim();
  if (!word) return showDialogError("단어를 입력해 주세요");
  const btn = $("wd-save");
  btn.disabled = true;
  try {
    await api.updateWord(state.editingId, {
      word,
      meaning: $("wd-meaning").value.trim(),
      example: $("wd-example").value.trim(),
    });
    $("word-dialog").close();
    await reload();
    showToast("단어를 수정했어요");
  } catch (e) {
    showDialogError(e.message);
  } finally {
    btn.disabled = false;
  }
}

// ---------- 연결 ----------
export function init() {
  $("word-form").addEventListener("submit", submitDialog);
  $("wd-cancel").addEventListener("click", () => $("word-dialog").close());
  $("word-sort").addEventListener("change", (e) => {
    state.sort = e.target.value;
    reload();
  });
  $("word-search").addEventListener("input", (e) => {
    state.query = e.target.value;
    renderList();
  });
  // 밀어 둔 줄은 바깥을 누르면 닫는다
  document.addEventListener("pointerdown", (e) => {
    if (state.openRow && !e.target.closest(".swipe")) closeOpenRow();
  });
}

/** 이 화면이 보일 때마다 최신 상태로 불러온다. "방금 등록"은 이때 한 번만 꺼낸다. */
export function show() {
  state.justAdded = takeJustAdded();
  reload();
}
