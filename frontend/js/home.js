// 홈 화면: 오늘의 복습 카드(3상태)와 "N일 연속" 배지
import { api } from "./api.js";

const $ = (id) => document.getElementById(id);

function renderReview(res) {
  const sub = $("home-review-sub");
  const link = $("home-review-link");
  const linkText = $("home-review-link-text");
  if (res.completed_today) {
    // 오늘 복습을 마침: 시작 버튼 없음
    sub.textContent = `오늘 복습 완료 · ${res.passed_count}개를 외웠어요`;
    link.hidden = true;
  } else if (res.count > 0) {
    sub.textContent = `복습할 단어가 ${res.count}개 있어요`;
    link.href = "#/review";
    linkText.textContent = "복습 시작";
    link.hidden = false;
  } else {
    sub.textContent = "오늘 복습할 단어가 없어요";
    link.href = "#/word-add";
    linkText.textContent = "단어 등록하러 가기";
    link.hidden = false;
  }
}

async function loadReview() {
  try {
    renderReview(await api.reviewToday());
  } catch (e) {
    $("home-review-sub").textContent = e.message;
    $("home-review-link").hidden = true;
  }
}

async function loadStreak() {
  try {
    const res = await api.getStreak();
    $("home-streak-text").textContent = `${res.streak}일 연속`;
    $("home-streak").hidden = false;
  } catch {
    $("home-streak").hidden = true; // 배지는 없어도 홈을 쓸 수 있다
  }
}

/** 홈이 보일 때마다 최신 상태로 */
export function show() {
  loadReview();
  loadStreak();
}
