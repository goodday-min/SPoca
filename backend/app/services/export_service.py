"""학습 기록 내보내기: 기록 목록을 CSV / JSON 파일 내용으로 바꾼다 (Firestore와 무관한 순수 변환)."""
import csv
import io
import json

HEADER = ["date", "value", "memo"]
# 엑셀이 수식으로 읽을 수 있는 시작 문자 (CSV 수식 주입 방지)
FORMULA_STARTS = ("=", "+", "-", "@")


def _safe_cell(text: str) -> str:
    return "'" + text if text.startswith(FORMULA_STARTS) else text


def to_csv(rows: list[dict]) -> str:
    """UTF-8 BOM 을 붙여 엑셀에서도 한글이 깨지지 않게 한다."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(HEADER)
    for r in rows:
        writer.writerow([r["date"], r["value"], _safe_cell(r.get("memo") or "")])
    return "\ufeff" + buf.getvalue()


def to_json(rows: list[dict]) -> str:
    items = [{"date": r["date"], "value": r["value"], "memo": r.get("memo") or ""} for r in rows]
    return json.dumps(items, ensure_ascii=False, indent=2)
