from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.db import init_db
from backend.routers import auth, problems, admin, export, system
from backend.core.config import PUBLIC_DIR
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Static Files
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由模块
# 我们使用 prefix 参数来为每个模块分配一个 URL 前缀
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(problems.router, prefix="/problems", tags=["problems"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(export.router)
app.include_router(system.router, prefix="/system", tags=["system"])
