"""Firestore 연결 모듈.

서비스 계정 키는 환경변수로만 받는다.
- FIREBASE_SERVICE_ACCOUNT_JSON : JSON 내용 전체 (배포 환경에서 사용)
- FIREBASE_SERVICE_ACCOUNT_PATH : JSON 파일 경로 (로컬 개발에서 사용)
둘 다 있으면 JSON 내용을 먼저 쓴다.
"""
import json
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.config import BACKEND_DIR, settings


def _load_credentials() -> credentials.Certificate:
    if settings.firebase_service_account_json:
        info = json.loads(settings.firebase_service_account_json)
        return credentials.Certificate(info)

    if settings.firebase_service_account_path:
        path = Path(settings.firebase_service_account_path)
        # 상대 경로는 서버를 어디서 실행하든 backend 폴더 기준으로 찾는다.
        if not path.is_absolute():
            path = BACKEND_DIR / path
        if not path.is_file():
            raise RuntimeError(f"서비스 계정 키 파일을 찾을 수 없어요: {path}")
        return credentials.Certificate(str(path))

    raise RuntimeError(
        "Firebase 서비스 계정 키가 설정되지 않았어요. "
        ".env 의 FIREBASE_SERVICE_ACCOUNT_PATH 또는 FIREBASE_SERVICE_ACCOUNT_JSON 을 채워 주세요."
    )


@lru_cache(maxsize=1)
def get_db():
    """Firestore 클라이언트를 돌려준다. 처음 호출할 때 한 번만 연결한다."""
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(_load_credentials())
    return firestore.client()
