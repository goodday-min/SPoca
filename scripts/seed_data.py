"""샘플 학습 기록(data)을 Firestore에 미리 넣는 시드 스크립트.

- 2026-05-28 ~ 2026-10-04 (130일) 중 쉬는 날을 빼고 100건 이상을 만든다.
- 이미 있는 날짜는 건드리지 않고 건너뛰므로 여러 번 실행해도 중복되지 않는다.
- 값은 고정된 난수(seed=42)로 만들어 실행할 때마다 같은 데이터가 나온다.

실행 (backend 폴더에서, 가상환경을 켠 상태로):
    python ../scripts/seed_data.py --dry-run   # 저장하지 않고 개수만 확인
    python ../scripts/seed_data.py             # 실제로 저장
"""
import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# backend/app 모듈을 가져올 수 있게 경로를 추가한다.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

START = date(2026, 5, 28)
END = date(2026, 10, 4)
MIN_RECORDS = 100
REST_PROBABILITY = 0.12  # 복습하지 않아 기록이 없는 날의 비율

MEMOS = [
    "복습 꾸준히",
    "시험 전날",
    "단어장 새로 등록",
    "집중이 잘 된 날",
    "피곤해서 조금만",
    "영어 대화 연습함",
    "주말 몰아서 복습",
    "책 스캔으로 단어 추가",
]


def build_records() -> list[dict]:
    rng = random.Random(42)
    total_days = (END - START).days + 1
    records = []
    for i in range(total_days):
        day = START + timedelta(days=i)
        if rng.random() < REST_PROBABILITY:
            continue  # 쉬는 날은 기록을 만들지 않는다.
        # 천천히 늘어나는 흐름(약 4 -> 11)에 요일 효과와 흔들림을 더한다.
        base = 4 + 7 * i / (total_days - 1)
        weekend = -1.5 if day.weekday() >= 5 else 0
        value = max(0, round(base + weekend + rng.gauss(0, 1.8)))
        memo = rng.choice(MEMOS) if rng.random() < 0.15 else ""
        records.append({"date": day.isoformat(), "value": value, "memo": memo})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="샘플 학습 기록을 Firestore에 넣는다.")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 개수만 보여준다")
    args = parser.parse_args()

    records = build_records()
    if len(records) < MIN_RECORDS:
        raise SystemExit(f"샘플이 {len(records)}건뿐이에요. 과제 기준({MIN_RECORDS}건)에 모자라요.")
    print(f"만든 샘플: {len(records)}건 ({records[0]['date']} ~ {records[-1]['date']})")

    if args.dry_run:
        print("--dry-run: 저장하지 않았어요.")
        return

    from app.core.firebase import get_db  # 연결이 필요할 때만 불러온다.

    col = get_db().collection("data")
    existing = {d.to_dict().get("date") for d in col.stream()}
    new_records = [r for r in records if r["date"] not in existing]
    print(f"이미 있는 날짜 {len(records) - len(new_records)}건은 건너뛰고, {len(new_records)}건을 저장해요.")

    # Firestore 일괄 쓰기는 한 번에 500개까지라서 나눠서 저장한다.
    for start in range(0, len(new_records), 400):
        batch = get_db().batch()
        for r in new_records[start:start + 400]:
            batch.set(col.document(), r)  # 문서 ID는 자동 생성
        batch.commit()
    print(f"완료: {len(new_records)}건 저장. 현재 data 컬렉션은 {len(existing) + len(new_records)}건이에요.")


if __name__ == "__main__":
    main()
