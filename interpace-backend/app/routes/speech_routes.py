"""语音面试 WebSocket 路由（对应 T7.6）。

浏览器建 WebSocket 时**带不了自定义请求头**，所以 access token 走查询参数
（`?token=...`），服务端用与 HTTP 接口同一套 JWT 校验逻辑验证身份与归属。

路由只做「鉴权 + 归属校验 + 交给编排服务」，业务逻辑在
`SpeechStreamService`（与其它路由的分层写法一致）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.logging_config import main_logger
from app.core.client_ip import resolve_client_ip_from_headers
from app.core.request_context import reset_request_context, set_request_context
from app.core.settings import settings
from app.db import get_db
from app.db.models import User
from app.security import decode_token
from app.services.session_service import SessionService
from app.services.speech_stream_service import SpeechStreamSession
from app.services.usage_quota_service import SCENE_VOICE
from app.services.usage_quota_service import UsageQuotaService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]

# WebSocket 关闭码：1008 = policy violation（鉴权 / 归属不通过时用）
WS_CLOSE_POLICY_VIOLATION = 1008


def _resolve_websocket_client_ip(websocket: WebSocket) -> str:
    """WebSocket 里的客户端 IP。

    复用 HTTP 侧的同一套口径（`client_ip.resolve_client_ip_from_headers`）——
    两边算法若不一致，同一个用户从 HTTP 和 WS 进来会被算成两个 IP，配额就各算一份。
    """
    peer_host = websocket.client.host if websocket.client else None
    return resolve_client_ip_from_headers(websocket.headers, peer_host)


def _authenticate(db: Session, token: str) -> User | None:
    """按 access token 取用户；无效返回 None（与 HTTP 依赖同一套校验口径）。"""
    if not token:
        return None
    try:
        payload = decode_token(
            token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except Exception:
        return None
    if payload.get("typ") != "access":
        return None
    user_id = int(payload.get("sub", 0) or 0)
    return db.get(User, user_id)


@router.websocket("/{session_id}/speech/stream")
async def speech_stream(
    websocket: WebSocket,
    session_id: int,
    db: DBSession,
    token: Annotated[str, Query(description="access token（浏览器 WebSocket 带不了请求头）")] = "",
    session_model: Annotated[int, Query(ge=0, le=2, description="会话归属：0 学习室 / 1 面试间")] = 1,
) -> None:
    """语音面试的流式通道：音频上行，识别文本与合成音频下行。"""
    # 演示环境可以在配置里整体关掉语音面试（T12.4）。前端不显示按钮只是界面，
    # 绕过界面直接连上来的请求才是真风险——语音是双计费（ASR 按时长 + TTS 按字符），
    # 最贵的一条链路。所以这里**在 accept 之前**就拒掉。
    if UsageQuotaService.voice_interview_disabled():
        await websocket.close(
            code=WS_CLOSE_POLICY_VIOLATION, reason="当前环境未开放语音面试"
        )
        return

    # 鉴权与归属校验必须在 accept 之前完成，否则等于给未授权连接开了门。
    user = _authenticate(db, token)
    if user is None:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="鉴权失败")
        return
    try:
        SessionService.get_session_or_404(
            db=db, user_id=user.id, session_id=session_id, session_model=session_model
        )
    except Exception:
        await websocket.close(code=WS_CLOSE_POLICY_VIOLATION, reason="会话不存在")
        return

    await websocket.accept()
    main_logger.info(
        f"[语音面试] WebSocket 已连接 user_id={user.id} session_id={session_id}"
    )
    # 语音面试不经过 HTTP 中间件（WebSocket 不走 @app.middleware("http")），
    # 所以这里自己把「谁 / 哪个 IP / 什么场景」放进上下文：
    # 场景标成 voice，配额按「语音分钟数」算，而不是和文字对话共用轮数额度。
    context_token = set_request_context(
        user_id=user.id,
        client_ip=_resolve_websocket_client_ip(websocket),
        scene=SCENE_VOICE,
    )
    session = SpeechStreamSession(
        websocket=websocket,
        user_id=user.id,
        session_id=session_id,
        session_model=session_model,
    )
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        main_logger.exception("[语音面试] WebSocket 会话异常结束", exc_info=exc)
    finally:
        reset_request_context(context_token)
        main_logger.info(
            f"[语音面试] WebSocket 已断开 user_id={user.id} session_id={session_id}"
        )
        try:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        except Exception:  # noqa: BLE001
            pass
