"""내보내기 단위 테스트 (Firestore 없이)"""
import csv
import io
import json

from fastapi.testclient import TestClient

from app.main import app
from app.routers import data as data_router
from app.services.export_service import to_csv, to_json

ROWS = [
    {"date": "2026-10-01", "value": 5, "memo": "첫날, \"쉼표\" 포함"},
    {"date": "2026-10-02", "value": 0, "memo": ""},
    {"date": "2026-10-03", "value": 7, "memo": "=SUM(A1)"},
]


def test_csv_has_bom_header_and_quotes():
    text = to_csv(ROWS)
    assert text.startswith("\ufeff")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    assert rows[0] == ["date", "value", "memo"]
    assert rows[1] == ["2026-10-01", "5", '첫날, "쉼표" 포함']
    assert rows[2] == ["2026-10-02", "0", ""]


def test_csv_formula_cell_is_neutralized():
    rows = list(csv.reader(io.StringIO(to_csv(ROWS).lstrip("\ufeff"))))
    assert rows[3][2] == "'=SUM(A1)"


def test_json_keeps_korean_and_fields():
    items = json.loads(to_json(ROWS))
    assert items[0] == {"date": "2026-10-01", "value": 5, "memo": '첫날, "쉼표" 포함'}
    assert "첫날" in to_json(ROWS)  # \u 이스케이프가 아님


def test_empty_export():
    assert list(csv.reader(io.StringIO(to_csv([]).lstrip("\ufeff")))) == [["date", "value", "memo"]]
    assert json.loads(to_json([])) == []


def test_endpoint_headers_and_range(monkeypatch):
    seen = {}

    def fake(start, end):
        seen["range"] = (start, end)
        return ROWS

    monkeypatch.setattr(data_router.data_service, "export_items", fake)
    c = TestClient(app)
    r = c.get("/api/data/export?format=csv&start=2026-10-01&end=2026-10-03")
    assert r.status_code == 200 and seen["range"] == ("2026-10-01", "2026-10-03")
    assert r.headers["content-type"].startswith("text/csv")
    assert "spoca_records_" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.csv"')
    j = c.get("/api/data/export?format=json")
    assert j.status_code == 200 and j.headers["content-disposition"].endswith('.json"')
    assert len(j.json()) == 3


def test_bad_format_and_date_are_422():
    c = TestClient(app)
    assert c.get("/api/data/export?format=xml").status_code == 422
    assert c.get("/api/data/export?start=abc").status_code == 422
