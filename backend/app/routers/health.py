from fastapi import APIRouter, HTTPException

from app.core.firebase import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """서버가 살아 있는지 확인한다. (배포 후 콜드스타트 확인에도 사용)"""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    """Firestore에 실제로 연결되는지 확인한다."""
    try:
        db = get_db()
        # 문서가 없어도 컬렉션을 한 번 읽어 보면 연결과 권한을 확인할 수 있다.
        list(db.collection("data").limit(1).stream())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Firestore 연결 실패: {exc}")
    return {"status": "ok", "database": "firestore"}
