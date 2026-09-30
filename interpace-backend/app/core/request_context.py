"""请求级上下文（对应 T12.3）。

为什么需要它：配额要按「谁 / 哪个 IP / 什么场景」记账，但这些信息只有**请求处理的最外层**
知道（用户来自 `get_current_user`，IP 来自 `Request`）。而真正的模型调用发生在深层服务里，
中间隔着好几层（chat_service → stream_chat_service → prompt_layer → llm）。

把 user_id / client_ip 在这些层之间一路当参数传下去，等于给七八个函数加两个与业务无关的参数，
而且**新增调用点时极容易漏传**——漏传的表现是"配额突然不生效"，而且没有任何报错。

`contextvars` 正好是干这个的：中间件在最外层设置一次，深层的 `llm.get_chat_model`
直接读，天然跟着请求走，也不会串到别的请求上（每个请求是一个独立的 context 拷贝）。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    """一次请求的身份信息。字段都可为空：后台任务、脚本里没有请求上下文。"""

    user_id: int | None = None
    client_ip: str | None = None
    # 业务场景（chat / quiz / evaluation / memory / resume …），由调用方按需覆盖。
    scene: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "interpace_request_context", default=None
)


def set_request_context(
    *,
    user_id: int | None = None,
    client_ip: str | None = None,
    scene: str | None = None,
) -> Token:
    """设置当前请求上下文，返回可用于还原的 token（中间件退出时重置）。"""
    return _request_context.set(
        RequestContext(user_id=user_id, client_ip=client_ip, scene=scene)
    )


def reset_request_context(token: Token) -> None:
    """还原上下文。中间件必须调用，否则线程复用时会串到下个请求。"""
    _request_context.reset(token)


def get_request_context() -> RequestContext | None:
    """读取当前请求上下文；不在请求里（脚本 / 定时任务）时返回 None。"""
    return _request_context.get()


def set_scene(scene: str) -> None:
    """在已有上下文里替换场景。

    场景在请求中途才会确定（例如流式对话要先解析出 select_model 才知道是
    「面试」还是「学习」），所以允许前置设置后再覆盖。
    """
    current = _request_context.get()
    if current is None:
        _request_context.set(RequestContext(scene=scene))
        return
    _request_context.set(
        RequestContext(
            user_id=current.user_id, client_ip=current.client_ip, scene=scene
        )
    )


def ensure_scene(default: str) -> str:
    """场景没被更外层定过时，才用 `default` 兜底。

    典型用法是对话主链路：语音面试会在连接建立时把场景标成 `voice`，
    这时候对话链路就不能再把它改回 `chat`——两者在配额上算的是不同额度
    （语音按分钟、文字按轮数）。
    """
    current = _request_context.get()
    if current is not None and current.scene:
        return current.scene
    set_scene(default)
    return default
