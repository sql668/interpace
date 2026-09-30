from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import register_exception_handlers
from app.core.client_ip import resolve_client_ip
from app.core.settings import settings
from app.core.logging_config import main_logger  # 导入日志配置
from app.core.request_context import reset_request_context, set_request_context
from app.db.base import Base
from app.db.database import engine, get_db
from app.security import decode_token
# 导入 Base 和 engine
from app.routes import auth_router, config_router, interview_router, note_router, profile_proposal_router, prompt_router, quiz_router, resource_router, resume_router, search_router, session_router, speech_router, user_profile_router, user_router, upload_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 表结构的**唯一权威是 Alembic 迁移**（T10.7 / D24）。
    #
    # 开发环境仍然 create_all 一次，图的是方便（跑测试、新拉代码即可用）；
    # 但**生产环境绝不自动建表**：create_all 只建缺失的表，既不会加列、也不会改类型，
    # 让它在生产跑只会掩盖「迁移没执行」这类问题——表面能用，实际 schema 是旧的
    # （真机就出现过：开发库 chat_messages.status 的注释是旧版，因为 create_all 从不改已有表）。
    if settings.app_env != "production":
        Base.metadata.create_all(engine)
        main_logger.info("开发环境：已用 create_all 补齐缺失的表（生产请改用 alembic upgrade head）")
    else:
        main_logger.info("生产环境：跳过 create_all，表结构由 Alembic 迁移负责")
    main_logger.info("应用启动完成，请通过此地址访问: http://127.0.0.1:8000")
    yield


app = FastAPI(title="User CRUD API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)


def _peek_user_id(request: Request) -> int | None:
    """从 Authorization 头里**非权威地**解出 user_id，只给用量记账用。

    真正的鉴权仍然由各接口的 `get_current_user` 负责，这里解不出来就当匿名。
    为什么不复用 `get_current_user`：它是**同步依赖**，FastAPI 会把它放到线程池里执行，
    而线程池里的 contextvar 修改**不会回传**给外层——在依赖里设置上下文，
    路由里读到的仍然是空的。所以身份信息必须在中间件这一层取。
    """
    header = request.headers.get("authorization") or ""
    prefix = "bearer "
    if not header.lower().startswith(prefix):
        return None
    try:
        payload = decode_token(
            header[len(prefix):].strip(),
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except Exception:  # noqa: BLE001 —— 令牌无效不在这里报错，交给真实鉴权
        return None
    if payload.get("typ") != "access":
        return None
    return int(payload.get("sub") or 0) or None


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """把「谁 / 哪个 IP」放进请求上下文（T12.3）。

    配额要按 IP 累计，而模型调用发生在很深的服务层，中间隔着七八层函数。
    在中间件设置一次，深层的 `llm.get_chat_model` 直接读，不用改任何函数签名。
    """
    token = set_request_context(
        user_id=_peek_user_id(request),
        client_ip=resolve_client_ip(request),
    )
    try:
        return await call_next(request)
    finally:
        # 必须还原：线程被复用时上下文会串到下个请求，配额就会算到别人头上。
        reset_request_context(token)

# 挂载静态文件目录
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 允许前端开发环境跨域访问（本地 + 局域网）
app.add_middleware(
    CORSMiddleware,
    # 白名单来自配置（CORS_ORIGINS）。生产环境是同源部署（Nginx 同时托管前端与反代 /api），
    # 浏览器根本不会发跨域请求，所以这里留空也不影响；只有前后端分域才需要显式配。
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 将用户相关接口统一挂载到 /users 前缀，便于路由分组与后续扩展版本。
# T10.1：全部业务接口统一收进 /api/v1（AGENTS.md 的接口规范）。
# 挂在一个 APIRouter 上而不是逐个写前缀，是为了以后加 /api/v2 时只需再挂一个 router，
# 现有的 prefix 一行都不用动。
API_V1_PREFIX = "/api/v1"

api_v1_router = APIRouter(prefix=API_V1_PREFIX)
api_v1_router.include_router(user_router, prefix="/users", tags=["users"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(upload_router, tags=["upload"])
api_v1_router.include_router(session_router, prefix="/sessions", tags=["sessions"])
api_v1_router.include_router(speech_router, prefix="/sessions", tags=["speech"])
api_v1_router.include_router(interview_router, prefix="/interviews", tags=["interviews"])
api_v1_router.include_router(prompt_router, prefix="/prompt", tags=["prompt_management"])
api_v1_router.include_router(note_router, prefix="/notes", tags=["notes"])
api_v1_router.include_router(quiz_router, prefix="/quiz-papers", tags=["quiz"])
api_v1_router.include_router(
    profile_proposal_router, prefix="/profile-proposals", tags=["profile_proposals"]
)
api_v1_router.include_router(resource_router, prefix="/resources", tags=["resources"])
api_v1_router.include_router(resume_router, prefix="/resumes", tags=["resumes"])
api_v1_router.include_router(search_router, prefix="/search", tags=["search"])
api_v1_router.include_router(user_profile_router, prefix="/profile", tags=["profile"])
# 运行时能力开关（T12.4）：前端据此决定界面上显示哪些入口。
api_v1_router.include_router(config_router, prefix="/config", tags=["config"])

app.include_router(api_v1_router)

# 刻意**不带版本前缀**的只有三类：探活、接口文档、根路径。
# 探活接口是给容器/负载均衡调用的，不该因为换 API 版本就跟着改地址。


@app.get("/")
def root() -> dict[str, str]:
    # 入口信息接口：仅确认服务可访问。
    main_logger.debug("根路径接口被访问。")
    return {"message": "FastAPI user service is running"}


@app.get("/health/live", summary="服务存活检查", tags=["stability"])
def health_live() -> dict[str, str]:
    # liveness 仅检查服务进程是否正常对外响应。
    return {"status": "healthy", "service": "running"}


@app.get("/health/ready", summary="服务就绪检查", tags=["stability"])
def health_ready(db: Session = Depends(get_db)) -> dict[str, object]:
    # readiness 检查核心依赖（数据库）是否可用。
    result: dict[str, object] = {
        "status": "healthy",
        "details": {
            "service": "running",
            "database": "connected",
        },
    }
    try:
        db.execute(text("SELECT 1"))
        return result
    except Exception:
        result["status"] = "unhealthy"
        result["details"] = {
            "service": "running",
            "database": "disconnected",
        }
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=result,
        )
