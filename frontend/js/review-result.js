// 복습 결과 화면: 외운 개수, 오늘 복습·다시 복습 개수, N일 연속, 다시 복습할 단어
import { getResult } from "./review.js";

const $ = (id) => document.getElementById(id);

function renderRetryList(items) {
  const list = $("rr-list");
  list.replaceChildren();
  for (const w of items) {
    const row = document.createElement("div");
    row.className = "word-row";
    const text = document.createElement("div");
    text.className = "word-text";
    const top = document.createElement("div");
    top.className = "word-top";
    const word = document.createElement("b");
    word.textContent = w.word;
    top.appendChild(word);
    if (w.status === "failed") {
      // Master까지 물었는데도 못 외워 끝난 단어 (다시 묻지 않는다)
      const end = document.createElement("span");
      end.className = "badge badge-failed";
      end.textContent = "종료";
      top.appendChild(end);
    }
    const meaning = document.createElement("span");
    meaning.className = w.meaning ? "word-meaning" : "word-meaning empty";
    meaning.textContent = w.meaning || "뜻 없음";
    text.append(top, meaning);
    row.appendChild(text);
    list.appendChild(row);
  }
  list.hidden = items.length === 0;
  $("rr-empty").hidden = items.length > 0;
}

export function show() {
  const r = getResult();
  if (!r) {
    // 결과가 없으면(새로고침 등) 복습 화면으로 돌려보낸다. 거기서 오늘 복습 상태를 보여 준다.
    location.hash = "#/review";
    return;
  }
  $("rr-big").textContent = `${r.passed_count}개를 외웠어요`;
  $("rr-streak").textContent = `${r.streak}일 연속!`;
  $("rr-reviewed").textContent = `${r.reviewed_count}개`;
  $("rr-retry").textContent = `${r.retry_count}개`;
  renderRetryList(r.retry_items);
}
