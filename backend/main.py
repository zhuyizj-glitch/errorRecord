"""错题集后端 - FastAPI 入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    if settings.ima_enabled:
        start_scheduler()
    yield
    # 关闭时
    stop_scheduler()


app = FastAPI(
    title="错题集 API",
    description="为两个孩子管理的多学科错题收集、分析与复习系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.routes import children, questions, upload, review, settings as settings_routes, stats, tasks, sync

app.include_router(children.router, prefix="/api", tags=["孩子"])
app.include_router(upload.router, prefix="/api", tags=["上传"])
app.include_router(questions.router, prefix="/api", tags=["错题"])
app.include_router(review.router, prefix="/api", tags=["复习"])
app.include_router(settings_routes.router, prefix="/api", tags=["设置"])
app.include_router(stats.router, prefix="/api", tags=["统计"])
app.include_router(tasks.router, prefix="/api", tags=["任务"])
app.include_router(sync.router, prefix="/api", tags=["同步"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "vault_path": settings.vault_path}
