import { showToast } from "./ui.js";
import * as records from "./records.js";
import * as chat from "./chat.js";

// 화면 전환: 주소의 #/이름 에 맞는 화면(section)만 보여 준다.
const DEFAULT_ROUTE = "home";

const views = document.querySelectorAll(".view");
const tabs = document.querySelectorAll(".tab");

function currentRoute() {
  const name = location.hash.replace(/^#\//, "");
  return document.querySelector(`.view[data-view="${name}"]`) ? name : DEFAULT_ROUTE;
}

// 화면이 보일 때마다 불러올 것이 있는 화면
const onShow = { report: records.show, coach: chat.show };

function render() {
  const route = currentRoute();
  views.forEach((v) => { v.hidden = v.dataset.view !== route; });
  document.body.dataset.route = route;
  tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === route));
  window.scrollTo(0, 0);
  onShow[route]?.();
}

records.init();
chat.init();
window.addEventListener("hashchange", render);
render();

// 홈: 영어 대화는 M4에서 만든다
document.getElementById("home-english")?.addEventListener("click", () =>
  showToast("영어 대화는 준비 중이에요")
);
