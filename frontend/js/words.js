// 단어장 목록 화면: 정렬, 단계 배지, 수정 팝업, 삭제, "방금 등록" 표시
import { api } from "./api.js";
import { showToast, withLoading } from "./ui.js";

const $ = (id) => document.getElementById(id);

const state = {
  items: [],
  sort: "latest", // "latest"(최신 등록순) | "stage"(단계순)
  editingId: null,
  justAdded: new Set(), // 이번에 처음 열 때 "방금 등록"을 붙일 단어 id
};

const EDIT_ICON = "M4 20l1-4L16 5l3 3L8 19zM14 7l3 3";
const DELETE_ICON = "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3";

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

function iconButton(label, pathD, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "icon-btn";
  b.setAttribute("aria-label", label);
  b.appendChild(icon(pathD));
  b.addEventListener("click", () => onClick(b));
  return b;
}

/** 단계 배지 글자와 색. 복습 중이면 단계 이름, 끝난 단어는 외움/못 외움 */
function badgeOf(item) {
  if (item.status === "passed") return { text: "외움", cls: "badge-passed" };
  if (item.status === "failed") return { text: "못 외움", cls: "badge-failed" };
  return { text: item.stage, cls: item.stage === "Master" ? "badge-master" : item.stage === "New" ? "badge-new" : "badge-step" };
}

const STATUS_LABEL = { reviewing: "복습 중", passed: "외움", failed: "못 외움" };

// ---------- 목록 ----------
function renderList() {
  const list = $("word-list");
  list.replaceChildren();
  for (const item of state.items) {
    const row = document.createElement("div");
    row.className = "word-row";

    const text = document.createElement("div");
    text.className = "word-text";

    const top = document.createElement("div");
    top.className = "word-top";
    const word = document.createElement("b");
    word.textContent = item.word;
    const badge = document.createElement("span");
    const b = badgeOf(item);
    badge.className = `badge ${b.cls}`;
    badge.textContent = b.text;
    top.append(word, badge);
    if (state.justAdded.has(item.id)) {
      const tag = document.createElement("span");
      tag.className = "badge badge-just";
      tag.textContent = "방금 등록";
      top.appendChild(tag);
    }

    const meaning = document.createElement("span");
    meaning.className = item.meaning ? "word-meaning" : "word-meaning empty";
    meaning.textContent = item.meaning || "뜻 없음";

    text.append(top, meaning);
    row.append(
      text,
      iconButton("수정", EDIT_ICON, () => openDialog(item)),
      iconButton("삭제", DELETE_ICON, (btn) => removeItem(item, btn))
    );
    list.appendChild(row);
  }
  $("word-count").textContent = `단어 ${state.items.length}개`;
  const msg = $("word-state");
  msg.hidden = state.items.length > 0;
  if (!state.items.length) msg.textContent = "아직 단어가 없어요. 위의 + 단어 등록으로 시작해 보세요";
  list.hidden = state.items.length === 0;
  document.querySelectorAll(".view[data-view='words'] .seg-btn").forEach((btn) => {
    const on = btn.dataset.sort === state.sort;
    btn.classList.toggle("on", on);
    btn.setAttribute("aria-selected", String(on));
  });
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
  $("word-info").textContent = `등록일 ${item.registered_date} · ${item.stage} 단계 · ${STATUS_LABEL[item.status]}`;
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
  document.querySelectorAll(".view[data-view='words'] .seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort;
      reload();
    })
  );
}

/** 이 화면이 보일 때마다 최신 상태로 불러온다. "방금 등록"은 이때 한 번만 꺼낸다. */
export function show() {
  state.justAdded = takeJustAdded();
  reload();
}
