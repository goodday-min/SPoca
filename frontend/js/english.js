// 영어 대화 화면: 책 사진 모으기(최대 3장) → 읽기 → 난이도 → 음성 대화 → 끝내기(단어 자동 등록)
// 대화는 서버에 저장하지 않는다. 책 내용과 지금까지의 대화는 이 화면이 들고 있다가 요청마다 같이 보낸다.
import { api } from "./api.js";
import { showToast } from "./ui.js";
import { shrink } from "./word-add.js";
import { markJustAdded } from "./words.js";

const $ = (id) => document.getElementById(id);

const MAX_PAGES = 3;
const NO_VOICE = "이 브라우저는 음성을 지원하지 않아요";
const BOT_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 14h.01M15 14h.01"/></svg>';

const state = {
  step: "scan", // "scan" | "level" | "talk"
  pages: [], // 줄인 사진 data URL
  bookText: "",
  level: "Beginner",
  messages: [], // [{role, content}]
  active: false, // 대화 중(나가면 사라지는 상태)
  busy: false, // AI 답을 기다리는 중
  finishing: false,
  listening: false,
  heard: "", // 마이크가 소리를 잡았는지: "" | "sound" | "speech"
  noSound: false, // 몇 초가 지나도 소리가 안 잡힘
  soundTimer: null,
  rec: null,
  startedAt: 0,
  timer: null,
  leaveTarget: null,
  replaceNext: false, // 다음에 고르는 사진으로 전부 바꾼다("사진 다시 고르기")
};
let pendingFile = null; // 홈에서 고른 사진: 영어 대화 화면이 열린 뒤 바로 읽는다

const speechRecognition = () => window.SpeechRecognition || window.webkitSpeechRecognition;
const hasVoice = () =>
  !!speechRecognition() && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

// ---------- 단계 전환 ----------
function setStep(step) {
  state.step = step;
  $("eng-step-scan").hidden = step !== "scan";
  $("eng-step-level").hidden = step !== "level";
  $("eng-step-talk").hidden = step !== "talk";
  $("eng-title").textContent = step === "level" ? "책 스캔" : "영어 대화";
  const talk = step === "talk";
  $("eng-timer").hidden = !talk;
  $("eng-end").hidden = !talk;
  window.scrollTo(0, 0);
}

// ---------- 사진 모으기 ----------
function renderPages() {
  const box = $("eng-pages");
  box.replaceChildren();
  state.pages.forEach((src, i) => {
    const item = document.createElement("div");
    item.className = "eng-page";
    const img = document.createElement("img");
    img.src = src;
    img.alt = `책 사진 ${i + 1}`;
    const del = document.createElement("button");
    del.type = "button";
    del.className = "eng-page-del";
    del.setAttribute("aria-label", `사진 ${i + 1} 빼기`);
    del.textContent = "×";
    del.addEventListener("click", () => {
      state.pages.splice(i, 1);
      hideScanError();
      renderPages();
    });
    item.append(img, del);
    box.appendChild(item);
  });
  box.hidden = state.pages.length === 0;
  const full = state.pages.length >= MAX_PAGES;
  const more = state.pages.length > 0;
  $("eng-camera").disabled = full;
  $("eng-gallery").disabled = full;
  $("eng-camera").textContent = more ? "페이지 추가 · 촬영" : "사진 찍기";
  $("eng-gallery").textContent = more ? "페이지 추가 · 갤러리" : "갤러리에서 고르기";
  $("eng-read").disabled = state.pages.length === 0;
}

function showScanError(message, canRetake) {
  const tip = $("eng-scan-error");
  tip.textContent = message;
  tip.hidden = false;
  $("eng-retake").hidden = !canRetake;
}

function hideScanError() {
  $("eng-scan-error").hidden = true;
  $("eng-retake").hidden = true;
}

/** 홈에서 "책 읽고 대화하기"를 누르면 사진 고르기 시트를 연다 */
export function openSource() {
  state.replaceNext = false;
  $("eng-source").showModal();
}

async function addFile(file) {
  hideScanError();
  try {
    const src = await shrink(file);
    if (state.replaceNext) state.pages = [];
    state.replaceNext = false;
    if (state.pages.length < MAX_PAGES) state.pages.push(src);
    renderPages();
    return true;
  } catch (e) {
    showScanError(e.message, false);
    return false;
  }
}

async function processFile(file) {
  $("eng-step-scan").classList.add("reading");
  const ok = await addFile(file);
  if (ok) await readPages();
  else $("eng-step-scan").classList.remove("reading");
}

async function onFilePicked(event) {
  const file = event.target.files[0];
  event.target.value = ""; // 같은 사진을 다시 골라도 반응하도록
  if (!file) return;
  if ($("eng-source").open) $("eng-source").close();
  if (location.hash !== "#/english") {
    // 홈에서 고른 경우: 영어 대화 화면으로 가서 바로 읽는다
    pendingFile = file;
    location.hash = "#/english";
    return;
  }
  setStep("scan");
  await processFile(file);
}

async function readPages() {
  if (!state.pages.length) return;
  const btn = $("eng-read");
  hideScanError();
  btn.disabled = true;
  btn.textContent = "사진을 읽는 중…";
  try {
    const res = await api.englishScan(state.pages);
    state.bookText = res.text;
    $("eng-done").textContent = `스캔 완료 · 문장 ${res.sentence_count}개 인식됨`;
    const hero = $("eng-hero");
    hero.replaceChildren();
    const himg = document.createElement("img");
    himg.src = state.pages[0];
    himg.alt = "스캔한 책 사진";
    hero.appendChild(himg);
    $("eng-addpage").hidden = state.pages.length >= MAX_PAGES;
    setStep("level");
  } catch (e) {
    $("eng-step-scan").classList.remove("reading");
    // 글자를 못 읽은 경우(422)는 다시 찍기를 안내한다
    showScanError(e.status === 422 ? "글자를 읽지 못했어요. 글자가 잘 보이게 다시 찍어 주세요" : e.message, e.status === 422);
  } finally {
    btn.textContent = "읽기";
    btn.disabled = state.pages.length === 0;
    $("eng-step-scan").classList.remove("reading");
  }
}

function retake() {
  state.pages = [];
  hideScanError();
  renderPages();
}

// ---------- 말풍선·상태 ----------
function addBubble(role, text) {
  const list = $("eng-messages");
  const bubble = document.createElement("div");
  bubble.className = "bubble" + (role === "user" ? " me" : "");
  bubble.textContent = text;
  if (role === "user") {
    list.appendChild(bubble);
  } else {
    const row = document.createElement("div");
    row.className = "msg-row";
    const ava = document.createElement("div");
    ava.className = "ava";
    ava.innerHTML = BOT_ICON;
    row.append(ava, bubble);
    list.appendChild(row);
  }
  list.scrollTop = list.scrollHeight;
  return bubble;
}

function setStatus(text) {
  $("eng-status").textContent = text;
}

function setMicState() {
  const mic = $("eng-mic");
  const wait = state.busy || state.finishing;
  mic.disabled = wait;
  mic.classList.toggle("on", state.listening);
  mic.setAttribute("aria-label", state.listening ? "말하기 끝내기" : "마이크를 눌러 말하기");
  $("eng-wave").hidden = !state.listening;
  if (state.finishing) return;
  if (state.listening) {
    if (state.heard === "speech") setStatus("듣고 있어요… 다 말했으면 한 번 더 눌러요");
    else if (state.noSound) setStatus("소리가 안 잡혀요. 마이크 연결과 권한을 확인해 주세요");
    else setStatus("듣는 중… 말해 보세요");
  }
  else if (state.busy) setStatus("AI가 생각하는 중…");
  else if (!$("eng-retry-row").hidden) setStatus("연결에 문제가 생겼어요");
  else setStatus("마이크를 눌러 말해 보세요");
}

// ---------- 읽어 주기 (AI 목소리) ----------
let speakDone = null;
let voiceCache = null;

/** 기계 느낌이 덜한 영어 목소리를 고른다 (브라우저·기기마다 있는 목소리가 달라 있는 것 중에서) */
function pickVoice() {
  if (voiceCache) return voiceCache;
  if (typeof window.speechSynthesis.getVoices !== "function") return null;
  const voices = window.speechSynthesis.getVoices().filter((v) => /^en[-_]US/i.test(v.lang));
  if (!voices.length) return null;
  const prefs = [/natural|neural|online/i, /google us english/i, /samantha|ava|allison|aria|jenny|zira|david/i];
  for (const re of prefs) {
    const v = voices.find((x) => re.test(x.name));
    if (v) return (voiceCache = v);
  }
  return (voiceCache = voices[0]);
}

function cancelSpeech() {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  if (speakDone) speakDone();
}

/** AI 답변을 소리 내어 읽고, 다 읽으면(또는 끊기면) 끝난다 */
function speakAndWait(text) {
  return new Promise((resolve) => {
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      clearTimeout(guard);
      speakDone = null;
      resolve();
    };
    // 어떤 이유로 끝 신호가 안 와도 멈춰 있지 않도록
    const guard = setTimeout(done, 4000 + text.length * 120);
    speakDone = done;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "en-US";
      const voice = pickVoice();
      if (voice) u.voice = voice;
      u.rate = 1.0;
      u.pitch = 1.05;
      u.onend = done;
      u.onerror = done;
      window.speechSynthesis.speak(u);
    } catch {
      done();
    }
  });
}

// ---------- 대화 ----------
function tickTimer() {
  const sec = Math.floor((Date.now() - state.startedAt) / 1000);
  $("eng-timer").textContent = `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
}

function startTalk() {
  state.messages = [];
  state.active = true;
  state.finishing = false;
  $("eng-messages").replaceChildren();
  $("eng-retry-row").hidden = true;
  $("eng-quit").hidden = true;
  state.startedAt = Date.now();
  tickTimer();
  clearInterval(state.timer);
  state.timer = setInterval(tickTimer, 1000);
  setStep("talk");
  turnAI();
}

/** 지금까지의 대화를 보내 AI 답을 받아 화면에 넣고 읽어 준다 */
async function turnAI() {
  if (state.finishing) return;
  state.busy = true;
  $("eng-retry-row").hidden = true;
  setMicState();
  try {
    const res = await api.englishChat(state.bookText, state.level, state.messages);
    if (!state.active) return; // 그 사이 나갔다
    state.messages.push({ role: "assistant", content: res.reply });
    addBubble("assistant", res.reply);
    state.busy = false;
    setMicState();
    await speakAndWait(res.reply);
    if (res.finished && state.active) finishConversation(); // AI가 마무리하면 자동으로 종료 흐름
  } catch (e) {
    if (!state.active) return;
    state.busy = false;
    $("eng-retry-row").hidden = false;
    showToast(e.message, { isError: true });
  } finally {
    state.busy = false;
    if (state.active) setMicState();
  }
}

function sendUser(text) {
  text = text.trim();
  if (!text || state.busy || state.finishing) return;
  state.messages.push({ role: "user", content: text });
  addBubble("user", text);
  turnAI();
}

// ---------- 마이크 소리 크기 표시 ----------
const meter = { stream: null, ctx: null, raf: 0, peak: 0 };

async function startMeter() {
  stopMeter();
  const bars = [...document.querySelectorAll("#eng-wave i")];
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!state.listening) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);
    meter.stream = stream;
    meter.ctx = ctx;
    meter.peak = 0;
    $("eng-wave").classList.add("live");
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) sum += ((v - 128) / 128) ** 2;
      const rms = Math.sqrt(sum / buf.length);
      meter.peak = Math.max(meter.peak, rms);
      const level = Math.min(1, rms * 8);
      bars.forEach((b, i) => {
        const k = 0.55 + 0.45 * Math.sin(Date.now() / 120 + i * 1.3);
        b.style.height = Math.max(4, Math.round(4 + level * 20 * k)) + "px";
      });
      if (rms > 0.02 && state.noSound) {
        state.noSound = false;
        setMicState();
      }
      meter.raf = requestAnimationFrame(tick);
    };
    tick();
  } catch (e) {
    console.warn("마이크 소리 크기를 읽지 못했어요:", e);
  }
}

function stopMeter() {
  cancelAnimationFrame(meter.raf);
  meter.stream?.getTracks().forEach((t) => t.stop());
  meter.ctx?.close?.().catch(() => {});
  meter.stream = null;
  meter.ctx = null;
  const wave = document.getElementById("eng-wave");
  wave?.classList.remove("live");
  wave?.querySelectorAll("i").forEach((b) => (b.style.height = ""));
}

// ---------- 마이크 (내가 말하기) ----------
function toggleMic() {
  if (state.busy || state.finishing) return;
  if (state.listening) {
    state.rec?.stop(); // 말을 마친 것으로 보고 보낸다
    return;
  }
  cancelSpeech(); // AI가 말하는 중이면 끊고 내 차례로
  const SR = speechRecognition();
  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  let finalText = "";
  let interimText = "";
  let draft = null;
  let hadError = false;
  const showDraft = () => {
    const text = (finalText + " " + interimText).trim();
    if (!text) return;
    if (!draft) {
      draft = addBubble("user", text);
      draft.classList.add("draft");
    } else {
      draft.textContent = text;
    }
    $("eng-messages").scrollTop = $("eng-messages").scrollHeight;
  };
  rec.onresult = (e) => {
    finalText = "";
    interimText = "";
    for (let i = 0; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript + " ";
      else interimText += r[0].transcript;
    }
    showDraft();
  };
  rec.onsoundstart = () => {
    state.heard = state.heard || "sound";
    state.noSound = false;
    setMicState();
  };
  rec.onspeechstart = () => {
    state.heard = "speech";
    state.noSound = false;
    setMicState();
  };
  rec.onerror = (e) => {
    console.warn("음성 인식 오류:", e.error);
    hadError = true;
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      showToast("마이크 사용을 허용해 주세요. (주소창 왼쪽 자물쇠 → 마이크 허용 후 새로고침)", { isError: true });
    } else if (e.error === "audio-capture") {
      showToast("마이크를 찾을 수 없어요. 연결과 기본 입력 장치를 확인해 주세요", { isError: true });
    } else if (e.error === "network") {
      showToast("음성 인식 서버에 연결할 수 없어요. 인터넷 연결을 확인해 주세요", { isError: true });
    } else if (e.error === "no-speech") {
      showToast("목소리가 들리지 않았어요. 마이크를 확인하고 다시 말해 주세요");
    } else if (e.error !== "aborted") {
      showToast("음성을 알아듣지 못했어요. 다시 말해 주세요", { isError: true });
    }
  };
  rec.onend = () => {
    clearTimeout(state.soundTimer);
    const quiet = meter.peak < 0.01;
    stopMeter();
    state.listening = false;
    state.heard = "";
    state.noSound = false;
    state.rec = null;
    draft?.remove();
    const text = (finalText + " " + interimText).trim();
    setMicState();
    if (text && state.active) sendUser(text);
    else if (!text && !hadError && state.active) {
      showToast(
        quiet
          ? "마이크 소리가 거의 안 들어와요. 브라우저·윈도우의 입력 장치와 볼륨을 확인해 주세요"
          : "소리는 들어왔는데 글자로 바꾸지 못했어요. 영어로 조금 더 또렷하게 말해 주세요",
        { isError: quiet },
      );
    }
  };
  try {
    rec.start();
    state.rec = rec;
    state.listening = true;
    state.heard = "";
    state.noSound = false;
    startMeter();
    clearTimeout(state.soundTimer);
    state.soundTimer = setTimeout(() => {
      if (state.listening && !state.heard && meter.peak < 0.02) {
        state.noSound = true;
        setMicState();
      }
    }, 5000);
    setMicState();
  } catch {
    showToast("마이크를 켤 수 없어요", { isError: true });
  }
}

// ---------- 끝내기 → 단어 등록 ----------
async function finishConversation() {
  if (state.finishing || !state.active) return;
  state.finishing = true;
  try {
    state.rec?.abort?.();
  } catch {
    /* 이미 끝난 경우 */
  }
  state.listening = false;
  stopMeter();
  cancelSpeech();
  clearInterval(state.timer);
  $("eng-retry-row").hidden = true;
  $("eng-wave").hidden = true;
  $("eng-mic").disabled = true;
  setStatus("대화에서 나온 단어를 정리하는 중…");
  try {
    const res = await api.englishFinish(state.bookText, state.messages);
    state.active = false;
    markJustAdded(res.items.map((w) => w.id)); // 단어장을 처음 열 때 "방금 등록" 표시
    showToast(res.count > 0 ? `단어 ${res.count}개를 단어장에 넣었어요` : "이번 대화에서는 등록할 단어가 없었어요");
    location.hash = "#/words";
  } catch (e) {
    state.finishing = false;
    setStatus(e.message);
    $("eng-retry").dataset.mode = "finish";
    $("eng-retry-row").hidden = false;
    $("eng-quit").hidden = false;
  }
}

function onRetry() {
  if ($("eng-retry").dataset.mode === "finish") {
    $("eng-retry").dataset.mode = "";
    finishConversation();
  } else {
    turnAI();
  }
}

// ---------- 나가기 확인 ----------
export function isActive() {
  return state.active && !state.finishing;
}

/** 대화 중에 다른 화면으로 가려 할 때 호출된다. 확인을 받고 갈 곳으로 이동한다. */
export function askLeave(target) {
  state.leaveTarget = target;
  if (!$("eng-leave").open) $("eng-leave").showModal();
}

function stopEverything() {
  clearInterval(state.timer);
  state.active = false;
  state.finishing = false;
  state.listening = false;
  clearTimeout(state.soundTimer);
  try {
    state.rec?.abort?.();
  } catch {
    /* 이미 끝난 경우 */
  }
  state.rec = null;
  stopMeter();
  cancelSpeech();
}

// ---------- 연결 ----------
function reset() {
  stopEverything();
  state.pages = [];
  state.bookText = "";
  state.level = "Beginner";
  state.messages = [];
  state.busy = false;
  hideScanError();
  renderPages();
  document.querySelectorAll(".eng-level").forEach((b) => {
    const on = b.dataset.level === "Beginner";
    b.classList.toggle("on", on);
    b.setAttribute("aria-checked", String(on));
  });
  $("eng-messages").replaceChildren();
  setStep("scan");
}

export function init() {
  $("eng-camera").addEventListener("click", () => $("eng-file-camera").click());
  $("eng-gallery").addEventListener("click", () => $("eng-file-gallery").click());
  $("eng-file-camera").addEventListener("change", onFilePicked);
  $("eng-file-gallery").addEventListener("change", onFilePicked);
  $("eng-read").addEventListener("click", readPages);
  $("eng-retake").addEventListener("click", retake);
  $("eng-rescan").addEventListener("click", () => {
    state.replaceNext = true;
    $("eng-source").showModal();
  });
  $("eng-addpage").addEventListener("click", () => {
    state.replaceNext = false;
    $("eng-source").showModal();
  });
  $("eng-src-camera").addEventListener("click", () => {
    $("eng-source").close();
    $("eng-file-camera").click();
  });
  $("eng-src-gallery").addEventListener("click", () => {
    $("eng-source").close();
    $("eng-file-gallery").click();
  });
  $("eng-src-close").addEventListener("click", () => $("eng-source").close());
  document.querySelectorAll(".eng-level").forEach((b) =>
    b.addEventListener("click", () => {
      state.level = b.dataset.level;
      document.querySelectorAll(".eng-level").forEach((x) => {
        const on = x === b;
        x.classList.toggle("on", on);
        x.setAttribute("aria-checked", String(on));
      });
    })
  );
  $("eng-start").addEventListener("click", startTalk);
  $("eng-mic").addEventListener("click", toggleMic);
  $("eng-end").addEventListener("click", finishConversation);
  $("eng-retry").addEventListener("click", onRetry);
  $("eng-quit").addEventListener("click", () => {
    stopEverything();
    location.hash = "#/home";
  });
  $("eng-leave-stay").addEventListener("click", () => $("eng-leave").close());
  $("eng-leave-go").addEventListener("click", () => {
    $("eng-leave").close();
    const target = state.leaveTarget || "#/home";
    reset(); // 대화는 버린다 (단어도 등록하지 않는다)
    location.hash = target;
  });
}

/** 이 화면에 들어올 때마다 처음부터. 음성을 못 쓰는 브라우저는 안내 문구만 보여 준다. */
export function show() {
  reset();
  const ok = hasVoice();
  $("eng-nosupport").hidden = ok;
  $("eng-step-scan").hidden = !ok;
  if (pendingFile && ok) {
    const f = pendingFile;
    pendingFile = null;
    processFile(f);
  }
  pendingFile = null;
}

/** 이 화면을 떠날 때 */
export function leave() {
  stopEverything();
}
