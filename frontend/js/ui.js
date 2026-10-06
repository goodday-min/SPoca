// 공통 화면 도구: 토스트(알림 문구), 로딩 표시

let toastTimer = null;

/** 화면 아래쪽에 잠깐 떴다 사라지는 안내 문구 */
export function showToast(message, { isError = false, ms = 3000 } = {}) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.setAttribute("role", "status");
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

/**
 * 버튼을 누르고 기다리는 동안 버튼을 잠그고(중복 클릭 방지) 끝나면 풀어 준다.
 * 오류가 나면 토스트로 보여 준다. 성공하면 fn의 결과를 돌려준다.
 */
export async function withLoading(button, fn) {
  if (button) {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  }
  try {
    return await fn();
  } catch (e) {
    showToast(e.message || "문제가 생겼어요", { isError: true });
    return undefined;
  } finally {
    if (button) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }
}

// --- 콜드스타트 안내 ---
export const WAKING_MESSAGE = "서버를 깨우는 중이라 조금 걸려요";
const SLOW_AFTER_MS = 3000; // 응답이 이 시간보다 늦으면 안내를 띄운다
let slowCount = 0;

function updateBanner() {
  const el = document.getElementById("wake-banner");
  if (el) el.hidden = slowCount === 0;
}

/**
 * 요청을 시작할 때 부르고, 돌려받은 함수를 요청이 끝나면(성공·실패 모두) 부른다.
 * 3초가 지나도 안 끝났으면 화면 위에 안내 줄을 보여 주고, 끝나면 숨긴다.
 */
export function trackSlowRequest() {
  let slow = false;
  const timer = setTimeout(() => {
    slow = true;
    slowCount += 1;
    updateBanner();
  }, SLOW_AFTER_MS);
  return () => {
    clearTimeout(timer);
    if (slow) {
      slowCount -= 1;
      updateBanner();
    }
  };
}

// --- 날짜 도구 (한국 시간 기준 YYYY-MM-DD) ---
export function todayKst() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

/** YYYY-MM-DD 에 days일을 더한 날짜 */
export function addDays(dateStr, days) {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** 단계 표기 (저장 값은 그대로 New/V1/V2/V3/Master, 화면에서만 바꿔 보여 준다) */
export const STAGE_LABEL = { New: "New", V1: "V", V2: "VV", V3: "VVV", Master: "Master" };

const NO_SPEECH = "이 브라우저는 음성을 지원하지 않아요";

/** 영어 단어 발음 듣기 (브라우저 음성 합성) */
export function speak(text) {
  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    showToast(NO_SPEECH);
    return;
  }
  window.speechSynthesis.cancel(); // 앞 소리가 남아 있으면 끊고 새로 읽는다
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 0.9;
  window.speechSynthesis.speak(u);
}
