// 리포트 화면: 기간 선택(7일/월별/전체), 요약 카드, 일별 그래프, 단어 단계 분포
import { api } from "./api.js";
import { todayKst, STAGE_LABEL } from "./ui.js";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";

const state = {
  period: "7d",
  month: todayKst().slice(0, 7), // YYYY-MM (월별 보기)
  report: null,
  picked: null, // 그래프에서 눌러 고른 칸의 index
  token: 0, // 느린 응답이 나중에 도착해 화면을 덮어쓰지 않게
};

const dash = (v) => (v === null || v === undefined ? "-" : String(v));

// ---------- 날짜 표시 ----------
function shortDate(iso) {
  const [, m, d] = iso.split("-");
  return `${Number(m)}/${Number(d)}`;
}

function monthLabel(ym) {
  const [y, m] = ym.split("-");
  return `${y}년 ${Number(m)}월`;
}

function shiftMonth(ym, delta) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

// ---------- 요약 카드 ----------
function renderSummary(r) {
  const s = r.summary;
  $("rp-period").textContent = s.period.start ? `기간 ${s.period.start} ~ ${s.period.end}` : "기록 없음";
  $("rp-count").textContent = s.count;
  $("rp-avg").textContent = dash(s.average);
  $("rp-max").textContent = dash(s.max);
  $("rp-min").textContent = dash(s.min);
  if (r.period === "7d") {
    $("rp-trend-label").textContent = "최근 추세";
    $("rp-trend").textContent = s.trend;
    $("rp-trend").classList.remove("faint");
  } else {
    // 추세는 최근 7일 보기에서만 보여 준다
    $("rp-trend-label").textContent = "추세";
    $("rp-trend").textContent = "추세는 7일 보기에서";
    $("rp-trend").classList.add("faint");
  }
}

// ---------- 그래프 (SVG) ----------
function el(name, attrs = {}, text) {
  const n = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}

const W = 320;
const H = 190;
const PAD = { l: 8, r: 8, t: 22, b: 26 };

function niceMax(maxValue) {
  return Math.max(5, Math.ceil(maxValue / 5) * 5);
}

function pickText(item) {
  return item.value === null ? `${shortDate(item.date)} · 기록 없음` : `${shortDate(item.date)} · ${item.value}개`;
}

function setPick(index) {
  state.picked = index;
  const items = state.report.daily;
  const pick = $("rp-pick");
  pick.hidden = false;
  pick.textContent = index === null ? "그래프를 눌러 날짜별 값을 확인해 보세요" : pickText(items[index]);
  document.querySelectorAll("#rp-chart [data-i]").forEach((n) => {
    n.classList.toggle("picked", Number(n.dataset.i) === index);
  });
}

function xLabels(daily, period) {
  // 보여 줄 날짜 라벨의 index 목록
  const n = daily.length;
  if (period === "7d") return daily.map((_, i) => i);
  if (period === "month") return daily.map((_, i) => i).filter((i) => i === 0 || (i + 1) % 5 === 0);
  const set = new Set([0, n - 1, Math.floor((n - 1) / 2)]);
  return [...set].sort((a, b) => a - b);
}

function renderChart(r) {
  const box = $("rp-chart");
  box.replaceChildren();
  const daily = r.daily;
  const pick = $("rp-pick");
  const recorded = daily.filter((d) => d.value !== null);

  if (!recorded.length) {
    pick.hidden = true;
    const p = document.createElement("p");
    p.className = "state-msg";
    p.textContent = "이 기간에는 기록이 없어요";
    box.appendChild(p);
    if (r.period !== "all") drawEmptyAxis(box, r); // 월별·7일은 빈 칸 틀은 보여 준다
    return;
  }

  const top = niceMax(Math.max(...recorded.map((d) => d.value)));
  const plotW = W - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;
  const y = (v) => PAD.t + plotH - (v / top) * plotH;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "rp-svg", role: "img", "aria-label": "일별 외운 단어 수 그래프" });
  const n = daily.length;
  const slot = plotW / n;
  const cx = (i) => PAD.l + slot * i + slot / 2;

  // 눈금: 0과 최대
  svg.append(el("line", { x1: PAD.l, x2: W - PAD.r, y1: y(0), y2: y(0), class: "rp-axis" }));
  svg.append(el("line", { x1: PAD.l, x2: W - PAD.r, y1: y(top), y2: y(top), class: "rp-grid" }));
  svg.append(el("text", { x: PAD.l, y: y(top) - 4, class: "rp-tick" }, String(top)));

  if (r.period === "all") {
    // 기록 있는 날만 이어서 그리는 선
    const pts = daily.map((d, i) => [cx(i), y(d.value)]);
    svg.append(el("polyline", { points: pts.map((p) => p.join(",")).join(" "), class: "rp-line" }));
    if (n <= 60) pts.forEach(([x, yy], i) => svg.append(el("circle", { cx: x, cy: yy, r: 2.6, class: "rp-dot", "data-i": i })));
    // 눌린 곳 표시용 점(많을 때도 보이도록)
    const mark = el("circle", { cx: -10, cy: -10, r: 4, class: "rp-mark" });
    svg.append(mark);
    svg._mark = mark;
    svg._pts = pts;
  } else {
    const barW = Math.min(28, slot * (r.period === "7d" ? 0.55 : 0.7));
    daily.forEach((d, i) => {
      if (d.value === null) return; // 기록 없는 날은 빈 칸
      const h = Math.max(1.5, (d.value / top) * plotH);
      svg.append(el("rect", { x: cx(i) - barW / 2, y: y(0) - h, width: barW, height: h, rx: Math.min(4, barW / 2), class: "rp-bar", "data-i": i }));
      if (r.period === "7d") svg.append(el("text", { x: cx(i), y: y(0) - h - 4, class: "rp-val" }, String(d.value)));
    });
  }

  // 가로 라벨
  for (const i of xLabels(daily, r.period)) {
    const anchor = r.period === "all" && i === 0 ? "start" : r.period === "all" && i === n - 1 ? "end" : "middle";
    const x = r.period === "all" ? (anchor === "start" ? PAD.l : anchor === "end" ? W - PAD.r : cx(i)) : cx(i);
    svg.append(el("text", { x, y: H - 8, class: "rp-x", "text-anchor": anchor }, r.period === "month" ? String(Number(daily[i].date.slice(8))) : shortDate(daily[i].date)));
  }

  // 누르는 영역: 칸마다 투명 사각형 (좁은 막대·점도 쉽게 누르도록)
  daily.forEach((d, i) => {
    const hit = el("rect", { x: PAD.l + slot * i, y: 0, width: slot, height: H - PAD.b, class: "rp-hit", "data-hit": i });
    hit.addEventListener("click", () => {
      setPick(i);
      if (svg._mark) {
        svg._mark.setAttribute("cx", svg._pts[i][0]);
        svg._mark.setAttribute("cy", svg._pts[i][1]);
      }
    });
    svg.append(hit);
  });

  box.appendChild(svg);
  if (r.period === "7d") {
    pick.hidden = true; // 7일은 막대 위에 숫자가 이미 보인다
  } else {
    setPick(null);
  }
}

function drawEmptyAxis(box, r) {
  const svg = el("svg", { viewBox: `0 0 ${W} 40`, class: "rp-svg rp-svg-empty", "aria-hidden": "true" });
  svg.append(el("line", { x1: PAD.l, x2: W - PAD.r, y1: 30, y2: 30, class: "rp-axis" }));
  box.appendChild(svg);
}

// ---------- 단어 단계 분포 ----------
const STAGE_NAMES = ["New", "V1", "V2", "V3", "Master"];

function distRow(label, count, max, kind) {
  const row = document.createElement("div");
  row.className = "rp-dist-row";
  const name = document.createElement("span");
  name.className = "rp-dist-name";
  name.textContent = label;
  const track = document.createElement("div");
  track.className = "rp-track";
  const fill = document.createElement("div");
  fill.className = "rp-fill " + kind;
  fill.style.width = max > 0 ? `${(count / max) * 100}%` : "0%";
  track.appendChild(fill);
  const num = document.createElement("b");
  num.className = "rp-dist-num";
  num.textContent = `${count}개`;
  row.append(name, track, num);
  return row;
}

function renderDist(r) {
  const box = $("rp-dist");
  box.replaceChildren();
  const d = r.stage_distribution;
  const counts = [...STAGE_NAMES.map((s) => d.reviewing[s]), d.finished.passed, d.finished.failed];
  const total = counts.reduce((a, b) => a + b, 0);
  if (total === 0) {
    const p = document.createElement("p");
    p.className = "state-msg";
    p.textContent = "아직 단어가 없어요";
    box.appendChild(p);
    return;
  }
  const max = Math.max(...counts);
  const g1 = document.createElement("p");
  g1.className = "rp-dist-title";
  g1.textContent = "복습 중";
  box.appendChild(g1);
  STAGE_NAMES.forEach((s) => box.appendChild(distRow(STAGE_LABEL[s], d.reviewing[s], max, "stage")));
  const g2 = document.createElement("p");
  g2.className = "rp-dist-title";
  g2.textContent = "끝난 단어";
  box.appendChild(g2);
  box.appendChild(distRow("외움", d.finished.passed, max, "passed"));
  box.appendChild(distRow("못 외움", d.finished.failed, max, "failed"));
}

// ---------- 불러오기 ----------
function renderControls() {
  document.querySelectorAll("#rp-seg .seg-btn").forEach((b) => {
    const on = b.dataset.period === state.period;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  $("rp-month").hidden = state.period !== "month";
  $("rp-month-label").textContent = monthLabel(state.month);
}

async function load() {
  const token = ++state.token;
  renderControls();
  const msg = $("rp-state");
  msg.hidden = false;
  msg.textContent = "불러오는 중…";
  $("rp-body").hidden = true;
  try {
    const r = await api.getReport(state.period, state.period === "month" ? state.month : undefined);
    if (token !== state.token) return; // 그 사이 다른 보기를 골랐다
    state.report = r;
    renderSummary(r);
    renderChart(r);
    renderDist(r);
    msg.hidden = true;
    $("rp-body").hidden = false;
  } catch (e) {
    if (token !== state.token) return;
    msg.textContent = e.message;
  }
}

export function init() {
  document.querySelectorAll("#rp-seg .seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      if (state.period === b.dataset.period) return;
      state.period = b.dataset.period;
      load();
    })
  );
  $("rp-prev").addEventListener("click", () => {
    state.month = shiftMonth(state.month, -1);
    load();
  });
  $("rp-next").addEventListener("click", () => {
    state.month = shiftMonth(state.month, 1);
    load();
  });
}

/** 이 화면이 보일 때마다 최신 값으로 */
export function show() {
  load();
}
