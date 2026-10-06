// 오늘의 복습 화면: 단어 2열 그리드, 학습 방향 전환, 탭=못 외움(취소 불가), 발음 듣기, 복습 완료
import { api } from "./api.js";
import { showToast, speak } from "./ui.js";

const $ = (id) => document.getElementById(id);

const NO_MEANING = "뜻 없음";

const state = {
  date: null, // 지금 보고 있는 복습 날짜 (날짜가 바뀌면 탭 표시를 버린다)
  items: [],
  dir: "en2ko", // "en2ko"(영어→한글) | "ko2en"(한글→영어)
  tapped: new Set(), // 탭한(=못 외운) 단어 id. 한 번 탭하면 취소할 수 없다. 화면을 오가도 유지, 새로고침하면 처음부터
  busy: false,
  result: null, // 방금 복습을 마친 결과 (결과 화면이 읽는다)
};

/** 결과 화면이 읽는 방금 복습 결과. 새로고침하면 사라진다. */
export function getResult() {
  return state.result;
}

const SPEAKER_ICON = "M4 10v4h4l5 4V6L8 10zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11";

function svgIcon(pathD) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  svg.appendChild(path);
  return svg;
}

// ---------- 그리드 ----------
/**
 * 한 칸의 내용을 정한다.
 * - 영어→한글: 칸에 단어, 탭하면 뜻(없으면 "뜻 없음")이 나온다. 발음 아이콘은 처음부터.
 * - 한글→영어: 칸에 뜻, 탭하면 영어 단어가 나온다. 발음 아이콘은 영어가 보인 뒤에만(정답이 미리 들리지 않게).
 *   뜻이 비어 있으면 칸에 영어 단어를 그대로 보이고 "뜻 없음" 표시를 붙인다.
 */
function cellContent(item, tapped) {
  if (state.dir === "en2ko") {
    return { main: item.word, mainEmpty: false, answer: tapped ? item.meaning || NO_MEANING : null, answerEmpty: tapped && !item.meaning, speakable: true };
  }
  if (!item.meaning) {
    return { main: item.word, mainEmpty: false, note: NO_MEANING, answer: null, speakable: true };
  }
  return { main: item.meaning, mainEmpty: false, answer: tapped ? item.word : null, answerEmpty: false, speakable: tapped };
}

function renderCell(item) {
  const tapped = state.tapped.has(item.id);
  const c = cellContent(item, tapped);

  const cell = document.createElement("div");
  cell.className = "rv-cell" + (tapped ? " tapped" : "");
  cell.setAttribute("role", "button");
  cell.tabIndex = 0;
  cell.setAttribute("aria-pressed", String(tapped));

  const main = document.createElement("div");
  main.className = "rv-main";
  main.textContent = c.main;
  cell.appendChild(main);

  if (c.note) {
    const note = document.createElement("div");
    note.className = "rv-note";
    note.textContent = c.note;
    cell.appendChild(note);
  }
  if (c.answer) {
    const ans = document.createElement("div");
    ans.className = "rv-answer" + (c.answerEmpty ? " empty" : "");
    ans.textContent = c.answer;
    cell.appendChild(ans);
  }
  if (tapped) {
    const tag = document.createElement("span");
    tag.className = "rv-tag";
    tag.textContent = "다시복습";
    cell.appendChild(tag);
  }
  if (c.speakable) {
    const sp = document.createElement("button");
    sp.type = "button";
    sp.className = "rv-speak";
    sp.setAttribute("aria-label", `${item.word} 발음 듣기`);
    sp.appendChild(svgIcon(SPEAKER_ICON));
    sp.addEventListener("click", (e) => {
      e.stopPropagation(); // 발음을 듣는 것은 "탭"(못 외움)이 아니다
      speak(item.word);
    });
    cell.appendChild(sp);
  }

  const tap = () => {
    if (state.tapped.has(item.id)) return; // 한 번 탭하면 취소할 수 없다
    state.tapped.add(item.id);
    renderGrid();
  };
  cell.addEventListener("click", tap);
  cell.addEventListener("keydown", (e) => {
    if (e.target === cell && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      tap();
    }
  });
  return cell;
}

function renderGrid() {
  $("rv-grid").replaceChildren(...state.items.map(renderCell));
  $("rv-complete").textContent = `복습 완료 · ${state.tapped.size}개 다시 복습`;
}

function renderDirection() {
  document.querySelectorAll("#rv-body .seg-btn").forEach((b) => {
    const on = b.dataset.dir === state.dir;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
}

// ---------- 화면 상태 ----------
function showMessage(title, sub, withLink = false) {
  $("rv-body").hidden = true;
  $("rv-footer").hidden = true;
  $("rv-count").hidden = true;
  $("rv-state").hidden = true;
  $("rv-message-title").textContent = title;
  $("rv-message-sub").textContent = sub;
  $("rv-message-link").hidden = !withLink;
  $("rv-message").hidden = false;
}

function showError(message) {
  $("rv-body").hidden = true;
  $("rv-footer").hidden = true;
  $("rv-message").hidden = true;
  $("rv-count").hidden = true;
  const el = $("rv-state");
  el.textContent = message;
  el.hidden = false;
}

async function load() {
  if (!state.items.length) {
    $("rv-message").hidden = true;
    const el = $("rv-state");
    el.textContent = "불러오는 중…";
    el.hidden = false;
  }
  try {
    const res = await api.reviewToday();
    if (state.date !== res.date) state.tapped.clear(); // 새 날이면 어제 탭 표시는 버린다
    state.date = res.date;
    state.items = res.items;
    const ids = new Set(res.items.map((i) => i.id));
    state.tapped = new Set([...state.tapped].filter((id) => ids.has(id))); // 사라진 단어의 표시는 정리
    if (res.completed_today) {
      return showMessage("오늘 복습을 마쳤어요", `${res.passed_count}개를 외웠어요. 복습은 하루 한 번이에요`);
    }
    if (res.count === 0) {
      return showMessage("오늘 복습할 단어가 없어요", "단어를 등록하면 복습 일정이 만들어져요", true);
    }
    $("rv-message").hidden = true;
    $("rv-state").hidden = true;
    $("rv-count").textContent = `${res.count}개`;
    $("rv-count").hidden = false;
    renderDirection();
    renderGrid();
    $("rv-body").hidden = false;
    $("rv-footer").hidden = false;
  } catch (e) {
    showError(e.message);
  }
}

// ---------- 복습 완료 ----------
async function complete() {
  if (state.busy) return;
  state.busy = true;
  const btn = $("rv-complete");
  btn.disabled = true;
  try {
    const res = await api.completeReview([...state.tapped]);
    state.tapped.clear();
    state.result = res;
    location.hash = "#/review-result"; // 결과 화면으로
  } catch (e) {
    showToast(e.message, { isError: true });
    if (e.status === 409) await load(); // 이미 마쳤거나 대상이 없는 경우: 화면을 최신으로
  } finally {
    state.busy = false;
    btn.disabled = false;
  }
}

// ---------- 연결 ----------
export function init() {
  document.querySelectorAll("#rv-body .seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      state.dir = b.dataset.dir; // 방향을 바꿔도 탭 표시는 그대로
      renderDirection();
      renderGrid();
    })
  );
  $("rv-complete").addEventListener("click", complete);
}

/** 이 화면이 보일 때마다 오늘 대상을 다시 불러온다 (탭 표시는 유지) */
export function show() {
  load();
}
