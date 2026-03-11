import time

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from app.router.routers import router as api_router
from app.services import session_manager as sm
from app.services.session_manager import SessionManager

app = FastAPI()

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    return response

# 集成API路由
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许访问的源
    allow_credentials=True, # 允许携带cookie
    allow_methods=["*"], # 允许的请求方法
    allow_headers=["*"], # 允许的请求头
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化会话管理器"""
    sm.session_manager = await SessionManager.create()
    print("会话管理器初始化完成")