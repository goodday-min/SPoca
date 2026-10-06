from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.routers import chat, conversations, data, english, health, report, review, streak, words

app = FastAPI(
    title="스포카 API",
    description="학습 기록(시계열) 요약을 바탕으로 코칭하는 AI 비서 백엔드",
    version="0.1.0",
)

register_error_handlers(app)  # 422 입력 오류를 한국어 한 줄로

# 허용한 프론트 주소에서 오는 요청만 받는다. (.env 의 ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(words.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(streak.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(english.router, prefix="/api")
