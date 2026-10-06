import * as records from "./records.js";
import * as chat from "./chat.js";
import * as words from "./words.js";
import * as wordAdd from "./word-add.js";
import * as review from "./review.js";
import * as reviewResult from "./review-result.js";
import * as home from "./home.js";
import * as report from "./report.js";
import * as english from "./english.js";
import { api } from "./api.js";
import * as theme from "./theme.js";

// 화면 전환: 주소의 #/이름 에 맞는 화면(section)만 보여 준다.
const DEFAULT_ROUTE = "home";

const views = document.querySelectorAll(".view");
const tabs = document.querySelectorAll(".tab");

function currentRoute() {
  const name = location.hash.replace(/^#\//, "");
  return document.querySelector(`.view[data-view="${name}"]`) ? name : DEFAULT_ROUTE;
}

// 화면이 보일 때마다 불러올 것이 있는 화면
const onShow = { records: records.show, report: report.show, coach: chat.show, words: words.show, "word-add": wordAdd.show, review: review.show, "review-result": reviewResult.show, home: home.show, english: english.show };

// 하단 탭에 없는 화면은 어느 탭 아래에 속하는지 (탭 강조용)
const TAB_OF = { "word-add": "words", "review-result": "review", records: "report" };

let lastRoute = null;

// 하단 "복습" 아이콘 위에 오늘 복습할 단어 수를 표시한다 (복습을 마쳤으면 숨김)
let badgeAt = 0;
async function refreshReviewBadge(force = false) {
  if (!force && Date.now() - badgeAt < 15000) return;
  badgeAt = Date.now();
  try {
    const r = await api.reviewToday();
    const n = r.completed_today ? 0 : r.count;
    const el = document.getElementById("review-badge");
    el.textContent = n > 99 ? "99+" : String(n);
    el.hidden = n === 0;
  } catch {
    /* 서버가 잠들어 있어도 화면은 그대로 둔다 */
  }
}

function render() {
  const route = currentRoute();
  // 영어 대화 중에 다른 화면으로 가려 하면(뒤로가기·하단 탭 포함) 먼저 확인을 받는다
  if (lastRoute === "english" && route !== "english") {
    if (english.isActive()) {
      const target = location.hash || "#/home";
      history.replaceState(null, "", "#/english"); // 화면은 그대로 두고
      english.askLeave(target);
      return;
    }
    english.leave();
  }
  lastRoute = route;
  views.forEach((v) => { v.hidden = v.dataset.view !== route; });
  document.body.dataset.route = route;
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === (TAB_OF[route] || route)));
  window.scrollTo(0, 0);
  onShow[route]?.();
  refreshReviewBadge(route === "review-result" || lastRoute === "review-result");
}

records.init();
chat.init();
words.init();
wordAdd.init();
review.init();
report.init();
english.init();
theme.init();
window.addEventListener("hashchange", render);
render();

// 홈: 영어 대화 시작
document.getElementById("home-english")?.addEventListener("click", () => {
  english.openSource();
});
