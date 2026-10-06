// 단어 등록 화면: 직접 입력 / 책 스캔, 등록일(오늘·내일·날짜 선택)
import { api } from "./api.js";
import { addDays, showToast, todayKst } from "./ui.js";

const $ = (id) => document.getElementById(id);

const MAX_SIDE = 1600; // 사진은 긴 변을 이 크기로 줄여서 보낸다 (서버 한도 안에 들어가도록)
const JPEG_QUALITY = 0.85;

const state = {
  mode: "manual", // "manual" | "scan"
  dateMode: "today", // "today" | "tomorrow" | "pick"
  image: null, // 줄인 사진(data URL)
  busy: false,
};

function showError(message) {
  const tip = $("wa-error");
  tip.textContent = message;
  tip.hidden = false;
}
const hideError = () => ($("wa-error").hidden = true);

// ---------- 방법·등록일 선택 ----------
function setMode(mode) {
  state.mode = mode;
  $("wa-manual").hidden = mode !== "manual";
  $("wa-scan").hidden = mode !== "scan";
  document.querySelectorAll(".view[data-view='word-add'] .seg-btn").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  hideError();
}

function setDateMode(mode) {
  state.dateMode = mode;
  document.querySelectorAll("#wa-dates .chip").forEach((c) => c.classList.toggle("on", c.dataset.date === mode));
  $("wa-pick-date").hidden = mode !== "pick";
  hideError();
}

/** 선택한 등록일. 오늘이면 비워서(서버가 오늘로 정한다) 보낸다. */
function chosenDate() {
  if (state.dateMode === "today") return { value: null };
  if (state.dateMode === "tomorrow") return { value: addDays(todayKst(), 1) };
  const v = $("wa-date").value;
  if (!v) return { error: "등록일을 선택해 주세요" };
  if (v < todayKst()) return { error: "등록일은 오늘이나 이후 날짜만 선택할 수 있어요" };
  return { value: v };
}

// ---------- 사진 ----------
function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("사진을 읽을 수 없어요. JPEG·PNG·WebP 사진을 골라 주세요"));
    };
    img.src = url;
  });
}

/** 사진을 긴 변 1600px 이하 JPEG로 줄여 data URL로 만든다 */
async function shrink(file) {
  const img = await loadImage(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff"; // 투명한 PNG가 검게 나오지 않도록
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", JPEG_QUALITY);
}

function setImage(dataUrl) {
  state.image = dataUrl;
  $("wa-preview").hidden = !dataUrl;
  $("wa-preview-img").src = dataUrl || "";
  $("wa-pick").textContent = dataUrl ? "다른 사진 선택" : "사진 선택 (촬영 · 갤러리)";
}

async function onFilePicked(event) {
  const file = event.target.files[0];
  event.target.value = ""; // 같은 사진을 다시 골라도 반응하도록
  if (!file) return;
  hideError();
  try {
    setImage(await shrink(file));
  } catch (e) {
    setImage(null);
    showError(e.message);
  }
}

// ---------- 등록 ----------
async function submit() {
  if (state.busy) return;
  hideError();
  const date = chosenDate();
  if (date.error) return showError(date.error);

  const btn = $("wa-submit");
  const label = btn.textContent;
  try {
    if (state.mode === "manual") {
      const word = $("wa-word").value.trim();
      if (!word) return showError("단어를 입력해 주세요");
      state.busy = true;
      btn.disabled = true;
      await api.createWord({
        word,
        meaning: $("wa-meaning").value.trim(),
        example: $("wa-example").value.trim(),
        registered_date: date.value,
      });
      showToast("단어를 등록했어요");
    } else {
      if (!state.image) return showError("사진을 먼저 선택해 주세요");
      state.busy = true;
      btn.disabled = true;
      btn.textContent = "사진을 읽는 중… (10~30초)";
      const res = await api.scanWords(state.image, date.value);
      showToast(`${res.count}개 등록했어요`);
    }
    location.hash = "#/words"; // 등록 후 목록으로
  } catch (e) {
    showError(e.message);
  } finally {
    state.busy = false;
    btn.disabled = false;
    btn.textContent = label;
  }
}

// ---------- 연결 ----------
export function init() {
  document.querySelectorAll(".view[data-view='word-add'] .seg-btn").forEach((b) =>
    b.addEventListener("click", () => setMode(b.dataset.mode))
  );
  document.querySelectorAll("#wa-dates .chip").forEach((c) => c.addEventListener("click", () => setDateMode(c.dataset.date)));
  $("wa-date").min = todayKst();
  $("wa-pick").addEventListener("click", () => $("wa-file").click());
  $("wa-file").addEventListener("change", onFilePicked);
  $("wa-clear").addEventListener("click", () => setImage(null));
  $("wa-submit").addEventListener("click", submit);
}

/** 화면이 열릴 때마다 입력을 비우고 처음 상태로 */
export function show() {
  for (const id of ["wa-word", "wa-meaning", "wa-example", "wa-date"]) $(id).value = "";
  $("wa-date").min = todayKst();
  setImage(null);
  setMode("manual");
  setDateMode("today");
}
