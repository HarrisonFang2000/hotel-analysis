"""
总路由注册
"""
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.system_api import router as system_router
from app.api.data_api import router as data_router
from app.api.import_export_api import router as io_router
from app.api.chart_api import router as chart_router


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(title="酒店数据分析系统", version="0.9.0")
    
    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(system_router)
    app.include_router(data_router)
    app.include_router(io_router)
    app.include_router(chart_router)
    
    # 挂载前端静态文件（兼容开发/打包两种模式）
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    dist_path = os.path.join(base_dir, "dist")
    if os.path.exists(dist_path):
        app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
    
    return app
