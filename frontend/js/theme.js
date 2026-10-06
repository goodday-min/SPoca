// 다크 모드: 홈 왼쪽 위 버튼으로 라이트↔다크. 선택은 이 브라우저에 기억한다 (기본은 라이트).
const KEY = "spoca.theme";
const root = document.documentElement;

function isDark() {
  return root.dataset.theme === "dark";
}

function paint() {
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.setAttribute("aria-pressed", String(isDark()));
    btn.setAttribute("aria-label", isDark() ? "라이트 모드로 바꾸기" : "다크 모드로 바꾸기");
  }
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", isDark() ? "#1F1B18" : "#FBF7F2");
}

function toggle() {
  if (isDark()) delete root.dataset.theme;
  else root.dataset.theme = "dark";
  try {
    localStorage.setItem(KEY, isDark() ? "dark" : "light");
  } catch {
    /* 저장소를 못 써도 이번 화면에서는 바뀐다 */
  }
  paint();
}

export function init() {
  document.getElementById("theme-toggle")?.addEventListener("click", toggle);
  paint();
}
