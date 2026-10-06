"""오늘 복습 대상 계산 테스트 (Firestore 없이, 단어 목록을 직접 만들어서)"""
from datetime import date, datetime, timezone

import pytest

from app.services import review_service
from app.services.review_service import due_date, select_due


def word(wid, registered, stage="New", status="reviewing", created=0):
    return {
        "id": wid,
        "word": wid,
        "meaning": "",
        "example": "",
        "registered_date": registered,
        "stage": stage,
        "status": status,
        "created_at": datetime(2026, 10, 1, 0, 0, created, tzinfo=timezone.utc),
    }


def ids(items):
    return [w["id"] for w in items]


def test_due_dates_match_prd_example():
    # PRD F5: 10/5 등록 → 10/5, 10/6, 10/8, 10/12, 11/4
    got = [due_date("2026-10-05", s).isoformat() for s in ("New", "V1", "V2", "V3", "Master")]
    assert got == ["2026-10-05", "2026-10-06", "2026-10-08", "2026-10-12", "2026-11-04"]


def test_each_stage_is_asked_exactly_on_its_due_day():
    # 10/5 등록 단어가 각 단계로 올라와 있을 때, 복습일 전날은 안 나오고 당일부터 나온다
    for stage, day in [("V1", 6), ("V2", 8), ("V3", 12)]:
        w = [word("a", "2026-10-05", stage)]
        assert select_due(w, date(2026, 10, day - 1)) == []  # 복습일 전날은 아직
        assert ids(select_due(w, date(2026, 10, day))) == ["a"]  # 복습일 당일부터
    new = [word("a", "2026-10-05", "New")]
    assert select_due(new, date(2026, 10, 4)) == [] and ids(select_due(new, date(2026, 10, 5))) == ["a"]
    master = [word("a", "2026-10-05", "Master")]
    assert select_due(master, date(2026, 11, 3)) == []
    assert ids(select_due(master, date(2026, 11, 4))) == ["a"]


def test_future_registered_words_are_excluded():
    items = [word("today", "2026-10-06"), word("tomorrow", "2026-10-07"), word("later", "2026-11-01")]
    assert ids(select_due(items, date(2026, 10, 6))) == ["today"]


def test_finished_words_are_excluded():
    items = [word("a", "2026-10-01", status="passed"), word("b", "2026-10-01", status="failed"), word("c", "2026-10-01")]
    assert ids(select_due(items, date(2026, 10, 6))) == ["c"]


def test_missed_stage_is_asked_once_at_its_current_stage():
    # 10/1 등록, V1(10/2)·V2(10/4)를 놓치고 10/6에 복습: 가장 낮은 놓친 단계(V1)로 한 번만 나온다
    items = [word("a", "2026-10-01", "V1")]
    out = select_due(items, date(2026, 10, 6))
    assert len(out) == 1 and out[0]["stage"] == "V1" and out[0]["due_date"] == "2026-10-02"


def test_next_stage_schedule_stays_on_registered_date():
    # V1을 못 외워 V2로 올라갔는데 V2 복습일(10/4)이 이미 지났다 → 다음 복습(오늘)에 바로 나온다
    items = [word("a", "2026-10-01", "V2")]
    assert ids(select_due(items, date(2026, 10, 5))) == ["a"]


def test_order_is_earliest_registered_first_then_created_order():
    items = [
        word("c", "2026-10-05", created=3),
        word("a", "2026-10-01", "V3", created=9),
        word("b", "2026-10-05", created=1),
    ]
    assert ids(select_due(items, date(2026, 10, 8))) == ["a", "b", "c"]


def test_output_shape_has_no_internal_fields():
    out = select_due([word("a", "2026-10-06")], date(2026, 10, 6))[0]
    assert set(out) == {"id", "word", "meaning", "example", "registered_date", "stage", "due_date"}


# ---- 가짜 Firestore: 컬렉션 이름 → {문서ID: 필드} 로 메모리에 보관 -----------------------------
class FakeDoc:
    def __init__(self, ref, data):
        self.reference, self.id, self._data = ref, ref.id, data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data)


class FakeRef:
    def __init__(self, db, col, doc_id):
        self.db, self.col, self.id = db, col, doc_id

    def get(self):
        return FakeDoc(self, self.db.store[self.col].get(self.id))


class FakeQuery:
    def __init__(self, docs):
        self.docs = docs

    def where(self, filter=None, **kw):
        field, _, value = filter
        return FakeQuery([d for d in self.docs if d.to_dict().get(field) == value])

    def limit(self, n):
        return FakeQuery(self.docs[:n])

    def stream(self):
        return list(self.docs)


class FakeCol(FakeQuery):
    def __init__(self, db, name):
        self.db, self.name = db, name

    @property
    def docs(self):
        return [FakeDoc(FakeRef(self.db, self.name, i), d) for i, d in self.db.store[self.name].items()]

    def document(self, doc_id=None):
        self.db.counter += 1
        return FakeRef(self.db, self.name, doc_id or f"auto{self.db.counter}")


class FakeBatch:
    def __init__(self, db):
        self.db, self.ops = db, []

    def update(self, ref, data):
        self.ops.append(("update", ref, data))

    def set(self, ref, data):
        self.ops.append(("set", ref, data))

    def create(self, ref, data):
        self.ops.append(("create", ref, data))

    def commit(self):
        # 전부 성공하거나 전부 실패해야 하므로 먼저 검사하고 나서 적용한다
        for op, ref, _ in self.ops:
            exists = ref.id in self.db.store[ref.col]
            if (op == "create" and exists) or (op == "update" and not exists):
                raise RuntimeError("batch 실패")
        for op, ref, data in self.ops:
            if op == "update":
                self.db.store[ref.col][ref.id].update(data)
            else:
                self.db.store[ref.col][ref.id] = dict(data)


class FakeDb:
    def __init__(self, words=(), data=()):
        self.counter = 0
        self.store = {"words": {}, "data": {}, "reviews": {}}
        for w in words:
            self.store["words"][w["id"]] = {k: v for k, v in w.items() if k != "id"} | {"source": "manual"}
        for i, d in enumerate(data):
            self.store["data"][f"d{i}"] = dict(d)

    def collection(self, name):
        return FakeCol(self, name)

    def batch(self):
        return FakeBatch(self)


def with_fake(db):
    """review_service 가 이 가짜 DB를 쓰게 바꿔 끼운다. 되돌리는 함수를 돌려준다."""
    old_db, old_find, old_latest = review_service._db, review_service._find_data_doc, review_service._latest_review

    def find(d, day):
        docs = d.collection("data").where(filter=("date", "==", day)).limit(1).stream()
        return docs[0] if docs else None

    def latest(d):
        rows = list(d.store["reviews"].values())
        return max(rows, key=lambda r: r["date"]) if rows else None

    review_service._db, review_service._find_data_doc, review_service._latest_review = lambda: db, find, latest

    def undo():
        review_service._db, review_service._find_data_doc, review_service._latest_review = old_db, old_find, old_latest

    return undo


def run(db, fn, *args):
    undo = with_fake(db)
    try:
        return fn(*args)
    finally:
        undo()


T = date(2026, 10, 6)


def test_plan_pass_and_tap_transitions():
    due = [
        {"id": "p", "stage": "V1"},  # 탭 안 함 → 패스
        {"id": "t", "stage": "V1"},  # 탭함 → V2
        {"id": "m", "stage": "Master"},  # Master 탭 → 못 외움 종료
    ]
    plan = {p["id"]: p for p in review_service.plan_transitions(due, {"t", "m"}, T)}
    assert plan["p"]["changes"] == {"reviewed_at": "2026-10-06", "status": "passed", "passed_stage": "V1"}
    assert plan["t"]["changes"] == {"reviewed_at": "2026-10-06", "stage": "V2"}
    assert plan["m"]["changes"] == {"reviewed_at": "2026-10-06", "status": "failed"}


def test_today_review_before_any_review():
    db = FakeDb(words=[word("a", "2026-10-06")])
    out = run(db, review_service.today_review, T)
    assert out["date"] == "2026-10-06" and out["count"] == 1
    assert out["completed_today"] is False and out["passed_count"] == 0
    assert out["items"][0]["id"] == "a"


def test_complete_saves_words_data_and_review():
    db = FakeDb(
        words=[word("a", "2026-10-06"), word("b", "2026-10-06"), word("c", "2026-10-06"), word("future", "2026-10-09")],
        data=[{"date": "2026-10-05", "value": 3, "memo": "어제"}],
    )
    out = run(db, review_service.complete, ["b"], T)
    assert (out["reviewed_count"], out["passed_count"], out["retry_count"]) == (3, 2, 1)
    assert out["retry_items"] == [{"id": "b", "word": "b", "meaning": "", "stage": "V1", "status": "reviewing"}]
    w = db.store["words"]
    assert w["a"]["status"] == "passed" and w["a"]["passed_stage"] == "New" and w["a"]["reviewed_at"] == "2026-10-06"
    assert w["b"]["status"] == "reviewing" and w["b"]["stage"] == "V1"
    assert w["future"]["status"] == "reviewing" and w["future"]["stage"] == "New" and "reviewed_at" not in w["future"]
    # 오늘 기록이 없었으니 새로 만들고, 어제 기록은 그대로
    today_rec = [d for d in db.store["data"].values() if d["date"] == "2026-10-06"]
    assert today_rec == [{"date": "2026-10-06", "value": 2, "memo": ""}]
    assert any(d["date"] == "2026-10-05" and d["value"] == 3 for d in db.store["data"].values())
    r = db.store["reviews"]["2026-10-06"]
    assert r["reviewed_count"] == 3 and r["passed_count"] == 2 and r["retry_ids"] == ["b"]


def test_complete_keeps_memo_of_existing_today_record():
    db = FakeDb(words=[word("a", "2026-10-06")], data=[{"date": "2026-10-06", "value": 9, "memo": "직접 쓴 메모"}])
    run(db, review_service.complete, [], T)
    assert list(db.store["data"].values()) == [{"date": "2026-10-06", "value": 1, "memo": "직접 쓴 메모"}]


def test_complete_all_tapped_gives_zero_passed():
    db = FakeDb(words=[word("a", "2026-10-06"), word("b", "2026-10-06")])
    out = run(db, review_service.complete, ["a", "b"], T)
    assert out["passed_count"] == 0 and out["retry_count"] == 2
    assert [d["value"] for d in db.store["data"].values()] == [0]  # 복습을 했으니 0도 기록한다


def test_master_tapped_ends_as_failed_and_is_reported():
    db = FakeDb(words=[word("m", "2026-09-01", "Master")])
    out = run(db, review_service.complete, ["m"], T)
    assert db.store["words"]["m"]["status"] == "failed" and db.store["words"]["m"]["stage"] == "Master"
    assert out["retry_items"][0]["status"] == "failed"


def test_second_complete_on_same_day_is_rejected_and_nothing_changes():
    db = FakeDb(words=[word("a", "2026-10-06")])
    run(db, review_service.complete, [], T)
    before = {k: dict(v) for k, v in db.store["words"].items()}
    with pytest.raises(review_service.AlreadyReviewedError):
        run(db, review_service.complete, [], T)
    assert db.store["words"] == before


def test_today_review_after_completion_is_empty_but_shows_passed_count():
    db = FakeDb(words=[word("a", "2026-10-06"), word("b", "2026-10-06")])
    run(db, review_service.complete, ["b"], T)
    out = run(db, review_service.today_review, T)
    assert out["completed_today"] is True and out["passed_count"] == 1
    assert out["count"] == 0 and out["items"] == []


def test_nothing_to_review_is_rejected_and_nothing_saved():
    db = FakeDb(words=[word("future", "2026-10-09")])
    with pytest.raises(review_service.NothingToReviewError):
        run(db, review_service.complete, [], T)
    assert db.store["reviews"] == {} and db.store["data"] == {}


def test_tapped_id_not_in_today_targets_is_rejected():
    db = FakeDb(words=[word("a", "2026-10-06"), word("future", "2026-10-09")])
    for bad in (["future"], ["nope"], ["a", "nope"]):
        with pytest.raises(review_service.InvalidTappedWordsError):
            run(db, review_service.complete, bad, T)
    assert db.store["reviews"] == {} and db.store["words"]["a"]["status"] == "reviewing"


def test_missed_stage_word_moves_to_next_stage_with_registered_date_schedule():
    # 10/1 등록, V1(10/2) 놓치고 10/6에 복습하며 탭 → V2(복습일 10/4)로 가고, 이미 지났으니 다음 복습(10/7)에 바로 나온다
    db = FakeDb(words=[word("a", "2026-10-01", "V1")])
    run(db, review_service.complete, ["a"], T)
    assert db.store["words"]["a"]["stage"] == "V2"
    nxt = review_service.select_due(review_service._all_words(db), date(2026, 10, 7))
    assert [w["id"] for w in nxt] == ["a"] and nxt[0]["due_date"] == "2026-10-04"


# ---- 연속 학습 일수 ------------------------------------------------------------------------
def d(day):
    return date(2026, 10, day)


def review_row(day, streak):
    return {"date": f"2026-10-{day:02d}", "streak": streak, "passed_count": 1, "reviewed_count": 1, "retry_ids": []}


def test_first_ever_completion_starts_streak_at_1():
    db = FakeDb(words=[word("a", "2026-10-06")])
    out = run(db, review_service.complete, [], T)
    assert out["streak"] == 1 and db.store["reviews"]["2026-10-06"]["streak"] == 1


def test_consecutive_day_adds_one():
    db = FakeDb(words=[word("a", "2026-10-06")])
    db.store["reviews"]["2026-10-05"] = review_row(5, 3)
    assert run(db, review_service.complete, [], T)["streak"] == 4


def test_days_without_targets_keep_the_streak_and_each_adds_one():
    # 10/1에 복습(연속 2), 10/2~10/5는 복습 대상이 없던 날 4일 → 어제까지 6, 오늘 복습하면 7
    db = FakeDb(words=[word("a", "2026-10-06")])
    db.store["reviews"]["2026-10-01"] = review_row(1, 2)
    assert run(db, review_service.complete, [], T)["streak"] == 7


def test_missed_day_with_targets_breaks_the_streak():
    # 10/1 복습 때 탭한 단어가 V1(복습일 10/2)이 됐는데 10/2부터 안 했다 → 끊김, 오늘 복습하면 다시 1
    db = FakeDb(words=[word("a", "2026-10-01", "V1")])
    db.store["reviews"]["2026-10-01"] = review_row(1, 5)
    assert run(db, review_service.complete, [], T)["streak"] == 1


def test_streak_now_without_any_review_is_zero():
    out = review_service.streak_now(None, 0, [word("a", "2026-10-06")], T)
    assert out == {"streak": 0, "completed_today": False, "counts_today": False}
    # 단어가 하나도 없어도, 대상이 없는 날이어도 첫 복습 전에는 세지 않는다
    assert review_service.streak_now(None, 0, [], T)["streak"] == 0


def test_streak_now_after_completing_today_uses_stored_value():
    out = review_service.streak_now(d(6), 8, [], T)
    assert out == {"streak": 8, "completed_today": True, "counts_today": True}


def test_streak_now_with_target_today_not_done_shows_through_yesterday():
    out = review_service.streak_now(d(5), 7, [word("a", "2026-10-06")], T)
    assert out == {"streak": 7, "completed_today": False, "counts_today": False}


def test_streak_now_with_no_target_today_counts_today():
    # 마지막 복습 어제(연속 7), 오늘 복습할 단어 없음(내일 등록분만) → 오늘 +1 = 8
    out = review_service.streak_now(d(5), 7, [word("a", "2026-10-07")], d(6))
    assert out == {"streak": 8, "completed_today": False, "counts_today": True}
    # 복습 중인 단어가 아예 없어도 마찬가지
    assert review_service.streak_now(d(5), 7, [], d(6))["streak"] == 8


def test_streak_now_broken_shows_zero_until_today_review_done():
    out = review_service.streak_now(d(1), 5, [word("a", "2026-10-01", "V1")], T)
    assert out == {"streak": 0, "completed_today": False, "counts_today": False}


def test_overdue_stage_after_last_review_counts_as_target_from_next_day():
    # 10/5에 탭해서 V2(복습일 10/4, 이미 지남)가 됐다. 10/6(오늘)부터 대상 → 오늘은 아직 안 했으니 어제까지(=10/5) 값
    out = review_service.streak_now(d(5), 4, [word("a", "2026-10-01", "V2")], T)
    assert out["streak"] == 4 and out["counts_today"] is False
    # 10/3 복습 후 10/4부터 대상인 단어가 있는데 오늘(10/6)까지 안 했다 → 끊김
    assert review_service.streak_now(d(3), 4, [word("a", "2026-10-01", "V2")], T)["streak"] == 0


def test_get_streak_reads_latest_review_and_words():
    db = FakeDb(words=[word("a", "2026-10-07")])
    db.store["reviews"]["2026-10-04"] = review_row(4, 2)
    db.store["reviews"]["2026-10-05"] = review_row(5, 3)
    out = run(db, review_service.get_streak, T)
    assert out == {"date": "2026-10-06", "streak": 4, "completed_today": False, "counts_today": True}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("통과:", name)
    print("모두 통과")
