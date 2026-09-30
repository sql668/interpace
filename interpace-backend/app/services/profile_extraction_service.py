"""画像抽取服务：从简历内容里抽出结构化画像字段。

对应 T6.2（决策 D11）。抽取用的是「一次同步模型调用 + 约定 JSON」，
与刷题评分（T5.7）同一套路：不走流式，用户看不到这个过程，
抽出来的结果先落成「待确认」，用户确认后才写进 `user_profiles`。

为什么不让主回答直接吐 JSON：简历优化的正文是给人看的六节结构（T6.3），
把机器用的 JSON 混进去会毁掉排版；所以拆成第二次调用，各干各的事。
"""

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.prompt_layer import build_personalized_prompt
from app.core.logging_config import main_logger
from app.core.request_context import set_scene
from app.services.usage_quota_service import SCENE_RESUME
from app.services.usage_quota_service import UsageQuotaService

# 抽取用的内部 agent / 场景（对应 prompt_templates 里 seed 进去的模板）。
PROFILE_EXTRACTOR_AGENT = "resume_extractor"
RESUME_SCENE = "resume"

# 目标级别的预期取值，与 user_profiles.target_level 的注释一致。
LEVEL_VALUES = ("初级", "中级", "高级")

# 提示词与解析器共用同一份结构约定。
PROFILE_JSON_CONTRACT = (
    '{"target_job": "目标岗位或 null", "years_experience": "工作年限或 null", '
    '"target_level": "初级|中级|高级 或 null", '
    '"target_skills": ["技能1", "技能2"], '
    '"weak_topics": ["薄弱点1"]}'
)

# 模型常用来表达「没有」的写法，统一归一成 None，避免把「未知」当成岗位存进画像。
_NULL_TOKENS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "无",
    "未提供",
    "未知",
    "未指定",
    "暂无",
}

_CODE_FENCE_MARKERS = ("```json", "```JSON", "```")


@dataclass(frozen=True)
class ProfilePayload:
    """抽取出的画像字段；空字段一律为 None，不写空字符串。"""

    target_job: str | None = None
    years_experience: str | None = None
    target_level: str | None = None
    target_skills: list[str] | None = None
    weak_topics: list[str] | None = None

    @property
    def is_empty(self) -> bool:
        """一个字段都没抽出来时算空，调用方据此跳过落库。"""
        return not any(
            [
                self.target_job,
                self.years_experience,
                self.target_level,
                self.target_skills,
                self.weak_topics,
            ]
        )

    def to_payload(self) -> dict[str, Any]:
        """转成可存 JSON 的字典（字段与 user_profiles 对齐）。"""
        return {
            "target_job": self.target_job,
            "years_experience": self.years_experience,
            "target_level": self.target_level,
            "target_skills": list(self.target_skills or []),
            "weak_topics": list(self.weak_topics or []),
        }


def _strip_code_fence(text: str) -> str:
    """剥掉可能包裹 JSON 的 Markdown 代码块标记。"""
    stripped = text.strip()
    for marker in _CODE_FENCE_MARKERS:
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :]
            break
    if stripped.endswith("```"):
        stripped = stripped[: -len("```")]
    return stripped.strip()


def _extract_json_object(text: str) -> str | None:
    """取第一个 `{` 到最后一个 `}` 之间的内容。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalize_text(value: Any) -> str | None:
    """归一可选文本：空白与「未知」这类占位一律变 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _NULL_TOKENS else text


def _normalize_list(value: Any) -> list[str]:
    """归一字符串列表：去空白、去占位、去重且保持顺序。"""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        text = _normalize_text(entry)
        if text and text not in items:
            items.append(text)
    return items


def parse_profile_payload(text: str) -> ProfilePayload | None:
    """从模型输出里解析画像字段；解析不出来或全空时返回 None。

    与题库解析同一套容错口径（剥代码块、取首尾花括号、**不抛异常**）。
    """
    if not text or not text.strip():
        return None

    candidate = _extract_json_object(_strip_code_fence(text))
    if candidate is None:
        return None

    try:
        data = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    target_level = _normalize_text(data.get("target_level"))
    if target_level and target_level not in LEVEL_VALUES:
        # 不在预期取值里不算失败，原样保留，由用户确认环节自行改
        main_logger.warning(f"画像抽取返回了预期外的级别取值: {target_level}")

    payload = ProfilePayload(
        target_job=_normalize_text(data.get("target_job")),
        years_experience=_normalize_text(data.get("years_experience")),
        target_level=target_level,
        target_skills=_normalize_list(data.get("target_skills")),
        weak_topics=_normalize_list(data.get("weak_topics")),
    )
    return None if payload.is_empty else payload


def extract_profile(
    db: Session,
    *,
    user_id: int,
    resume_text: str,
    provider: str = "deepseek",
) -> ProfilePayload | None:
    """调一次模型抽取画像；失败或抽不出来都返回 None（由调用方决定跳过）。

    这里刻意**不抛异常**：抽取失败最多是「这次没有画像可确认」，
    不该影响用户已经拿到的简历优化结果。
    """
    # 演示环境的降本开关（T12.5）：画像抽取是用户看不见的额外模型调用，演示环境跳过。
    if UsageQuotaService.background_extraction_disabled():
        main_logger.debug("[画像抽取] 演示环境已关闭后台抽取，跳过")
        return None

    if not resume_text or not resume_text.strip():
        return None

    try:
        system_prompt = build_personalized_prompt(
            db=db,
            user_id=user_id,
            agent_name=PROFILE_EXTRACTOR_AGENT,
            scene=RESUME_SCENE,
        )
        if not system_prompt:
            # 模板没 seed 时兜底，保证链路可用（与其它链路口径一致）。
            system_prompt = (
                "你是信息抽取助手。从用户给的简历里抽出结构化字段，"
                "只输出约定格式的 JSON，抽不到的字段填 null，不要猜测。"
            )

        # 标记场景：简历场景下的画像抽取（属于后台抽取，演示环境可整体关掉）
        set_scene(SCENE_RESUME)
        model = get_chat_model(provider=provider)
        message = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": resume_text},
            ]
        )
        content = (
            message.content if isinstance(message.content, str) else str(message.content)
        )
        return parse_profile_payload(content)
    except Exception as exc:  # noqa: BLE001
        main_logger.warning(f"[画像抽取] 调用失败，本轮跳过: {exc!r}")
        return None
