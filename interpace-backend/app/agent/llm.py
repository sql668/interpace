"""模型工厂：统一创建聊天模型实例。

这是**全项目唯一的模型出口**（T12.3 的计量与 T12.4 的配额都挂在这里）。
为什么必须收口在这一层：一次用户提问可能触发多次模型调用（会话摘要压缩、画像抽取、
出题后的评分、记忆合并……），在接口入口按次数限流和真实的 token 消耗完全不是一回事。
所有调用点都经过 `get_chat_model`，所以在这里做检查与记账不会漏。
"""

from collections.abc import Callable

from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI

from app.agent.usage_callback import UsageRecordingCallback
from app.core.request_context import get_request_context
from app.core.settings import settings
from app.services.usage_quota_service import UsageQuotaService


# provider -> ChatOpenAI 构造函数（接一个回调列表用于计量）。
LlmFactory = Callable[[list[BaseCallbackHandler] | None], ChatOpenAI]

# provider -> 模型名。记账时要记下到底是哪个模型花的钱，
# 放在这里而不是写死 deepseek，是为了新增 provider 时不会记错。
_PROVIDER_MODEL_NAMES = {
    "deepseek": settings.deepseek_model,
}


def _build_deepseek_chat(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatOpenAI:
    """创建 DeepSeek(OpenAI兼容) 聊天模型。"""
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=settings.deepseek_temperature,
        # 演示环境会把单次输出上限压到配额配置里的值（降本开关）。
        max_tokens=UsageQuotaService.effective_max_tokens(settings.deepseek_max_tokens),
        streaming=True,
        # 打开后 provider 会在流式响应里带回用量，回调才拿得到真实 token 数。
        stream_usage=True,
        callbacks=callbacks,
    )


# 扩展口：后续新增 provider 只需在这里注册。
_PROVIDER_FACTORIES: dict[str, LlmFactory] = {
    "deepseek": _build_deepseek_chat,
}


def get_chat_model(provider: str = "deepseek") -> ChatOpenAI:
    """按 provider 返回聊天模型实例，并完成配额检查与用量记账。

    场景（chat / quiz / evaluation / …）从请求上下文里取，
    由各服务在调用前用 `request_context.set_scene()` 标记。
    **不通过函数参数传**：那样要给七八个函数加与业务无关的参数，
    而且新增调用点时极容易漏传——漏传的表现是配额静默失效，没有任何报错。
    """
    factory = _PROVIDER_FACTORIES.get(provider)
    if not factory:
        raise ValueError(f"Unsupported llm provider: {provider}")

    context = get_request_context()
    scene = (context.scene if context else None) or "unknown"
    client_ip = (context.client_ip if context else None) or ""
    user_id = context.user_id if context else None

    # 配额检查放在**建模型之前**：超额时连实例都不创建，直接 429。
    UsageQuotaService.check_before_call(scene=scene, client_ip=client_ip)

    callback = UsageRecordingCallback(
        scene=scene,
        client_ip=client_ip,
        user_id=user_id,
        provider=provider,
        model=_PROVIDER_MODEL_NAMES.get(provider, ""),
    )
    return factory(callbacks=[callback])
