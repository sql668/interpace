"""模型用量回调：把 provider 返回的真实 token 数写进 `usage_records`（T12.3）。

为什么用 LangChain 的 callback 而不是估算：

- 估算（按字符数除以 1.5 之类）在中文场景误差极大，而且**推理 token 根本估不出来**；
- 实测这条链路**流式与非流式都能拿到真实用量**，只是流式时它不在最后一帧，
  而在中间某一帧。所以必须挂回调累积，不能去读"最后一块 chunk"——
  这是一个很容易写错的点：按最后一块读会得到 `None`，然后整个配额系统静默失效。

callback 会随每次模型调用创建一个新实例（见 `llm.get_chat_model`），
构造时就把「谁 / 哪个 IP / 什么场景」定下来，所以调用结束时不需要再回查上下文。
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.core.logging_config import main_logger
from app.services.usage_quota_service import UsageQuotaService


def extract_usage(response: LLMResult) -> dict[str, int]:
    """从 LLMResult 里取出 token 用量，取不到返回全 0。

    两条来源都要试：新版 LangChain 放在 message 的 `usage_metadata`，
    老路径放在 `llm_output["token_usage"]`（OpenAI 原始字段名）。
    """
    for generation_list in response.generations or []:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            meta = getattr(message, "usage_metadata", None) if message else None
            if not meta:
                continue
            output_details = meta.get("output_token_details") or {}
            return {
                "prompt_tokens": int(meta.get("input_tokens") or 0),
                "completion_tokens": int(meta.get("output_tokens") or 0),
                "reasoning_tokens": int(output_details.get("reasoning") or 0),
                "total_tokens": int(meta.get("total_tokens") or 0),
            }

    token_usage = (response.llm_output or {}).get("token_usage") or {}
    if token_usage:
        completion_details = token_usage.get("completion_tokens_details") or {}
        return {
            "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
            "completion_tokens": int(token_usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(completion_details.get("reasoning_tokens") or 0),
            "total_tokens": int(token_usage.get("total_tokens") or 0),
        }

    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }


class UsageRecordingCallback(BaseCallbackHandler):
    """把一次模型调用的用量落到账本上。"""

    # 回调本身不抛异常：记账失败绝不能影响用户正在等的那次回答。
    raise_error = False

    def __init__(
        self,
        *,
        scene: str,
        client_ip: str,
        user_id: int | None,
        provider: str,
        model: str,
    ) -> None:
        self.scene = scene
        self.client_ip = client_ip
        self.user_id = user_id
        self.provider = provider
        self.model = model

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage = extract_usage(response)
        main_logger.debug(
            f"[用量] scene={self.scene} model={self.model} "
            f"prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} "
            f"reasoning={usage['reasoning_tokens']} total={usage['total_tokens']}"
        )
        UsageQuotaService.record(
            client_ip=self.client_ip,
            scene=self.scene,
            provider=self.provider,
            model=self.model,
            user_id=self.user_id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            reasoning_tokens=usage["reasoning_tokens"],
            total_tokens=usage["total_tokens"],
        )
