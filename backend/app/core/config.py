"""환경변수를 한 곳에서 읽는 설정 모듈.

비밀 값(API 키, 서비스 계정 키)은 코드에 쓰지 않고 backend/.env 또는
배포 환경(Render)의 환경변수로만 받는다.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# backend/.env 를 읽는다. (이미 설정된 환경변수는 덮어쓰지 않는다)
BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # CORS: 허용할 프론트 주소 목록
    allowed_origins: list[str]
    # Firebase 서비스 계정 키 (경로 또는 JSON 문자열 중 하나)
    firebase_service_account_path: str
    firebase_service_account_json: str
    # OpenAI 호환 API
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    # Anthropic 호환 API (사진 읽기용. 교육장은 OpenAI 호환 주소에서 사진 입력을 막아 둬서 이쪽을 쓴다)
    anthropic_api_key: str
    anthropic_base_url: str
    anthropic_vision_model: str


def get_settings() -> Settings:
    return Settings(
        allowed_origins=_split_csv(os.getenv("ALLOWED_ORIGINS", "")),
        firebase_service_account_path=os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", ""),
        firebase_service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://copa.codyssey.kr/v1"),
        anthropic_vision_model=os.getenv("ANTHROPIC_VISION_MODEL", "claude-sonnet-4"),
    )


settings = get_settings()
