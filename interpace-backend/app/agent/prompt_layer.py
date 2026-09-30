"""提示词层：统一组装 Prompt、记忆与编排图。

功能：
1. build_stream_graph - 组装 LangGraph 单节点编排图（提示词 + 历史 + 模型）
2. build_personalized_prompt - 带用户信息注入的个性化提示词
3. inject_user_info_to_template - 提示词动态填充
"""

from __future__ import annotations

import base64
from typing import Any, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.memory import (
    build_chat_history_from_rows,
    build_memory_context,
    get_latest_knowledge,
    should_recall,
)
from app.core.logging_config import main_logger
from app.core.request_context import ensure_scene
from app.db.models import ChatMessage
from app.services.attachment_content_service import AttachmentImage
from app.services.prompt_template_service import prompt_template_manager
from app.services.session_summary_service import (
    KEEP_RECENT,
    SessionSummaryService,
)
from app.services.usage_quota_service import SCENE_CHAT, UsageQuotaService
from app.services.user_profile_service import UserProfileService, get_injection_rule
from app.utils.prompt_logger import log_personalized_prompt_generated


class ChatGraphState(TypedDict, total=False):
    """单节点编排图的状态。

    - history：从数据库读出的最近若干轮历史消息（不含 system）
    - user_messages：本轮的用户消息（可能带图片内容块）
    - local_kb / search_result：保留的扩展输入，当前代码内置的提示词未引用它们，
      先原样透传以免影响将来使用这些变量的自定义模板
    """

    history: list[BaseMessage]
    user_messages: list[BaseMessage]
    local_kb: dict[str, str]
    search_result: str


def _build_user_message(
    request_text: str,
    attachment_text: str,
    attachment_images: list[AttachmentImage],
    memory_context: str = "",
) -> HumanMessage:
    """拼出本轮人类消息：附件正文 + 用户输入 + 图片内容块（多模态）。

    没有附件时就是一个纯文本内容块——统一走内容块数组，避免两套拼装逻辑。
    """
    blocks: list[dict[str, Any]] = []
    if memory_context:
        # 跨会话检索到的用户历史（T9.15）。明确告诉模型「无关就忽略」，
        # 否则它会硬把历史塞进回答，比检索不到更糟。
        blocks.append(
            {
                "type": "text",
                "text": (
                    "以下是检索到的该用户的历史记录（按相关度排序）。"
                    "如果与当前问题无关，忽略它，不要生搬硬套：\n\n" + memory_context
                ),
            }
        )
    if attachment_text:
        blocks.append(
            {"type": "text", "text": f"以下是用户上传的附件内容：\n{attachment_text}"}
        )
    blocks.append({"type": "text", "text": request_text})

    for image in attachment_images:
        # 图片以 data URL 内联：项目还没有资源对外提供接口，短期内只能这么传
        encoded = base64.b64encode(image.data).decode()
        blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image.mime_type};base64,{encoded}"},
            }
        )
    return HumanMessage(content=blocks)


def build_stream_graph(
    db: Session,
    user_id: int,
    session_id: int,
    current_message_id: int,
    provider: str,
    request_text: str,
    system_prompt: Optional[str] = None,
    attachment_text: str = "",
    attachment_images: Optional[list[AttachmentImage]] = None,
) -> tuple[CompiledStateGraph, dict[str, Any]]:
    """组装流式编排图，返回可执行的图与本轮输入。

    当前是一张单节点图（提示词 → 模型），与改造前的单链行为等价；
    后续多轮场景（刷题确认、模拟面试、复盘）直接在这张图里加节点即可。
    """
    # 1) 取最近 N 条历史消息（倒序拉取再反转，保证时间升序注入 prompt）。
    history_limit = KEEP_RECENT
    history_rows = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.session_id == session_id,
                ChatMessage.id < current_message_id,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(history_limit)
        )
    )
    history_rows.reverse()
    history = build_chat_history_from_rows(history_rows)

    # 1.5) 长会话压缩（T9.16）：更早的内容压成摘要，避免「第 3 轮说过的信息到第 30 轮就丢了」。
    #      这里只做一次「够不够触发」的判断，不够触发时几乎零成本。
    summary_text = ""
    #      演示环境可以整体关掉它（T12.5 降本开关）：这是一次用户看不见的额外模型调用。
    if UsageQuotaService.background_extraction_disabled():
        main_logger.debug("[上下文压缩] 演示环境已关闭后台压缩，本轮跳过")
    else:
        try:
            summary_text = SessionSummaryService.ensure_summary(
                db, user_id=user_id, session_id=session_id, provider=provider
            )
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"[上下文压缩] 失败，本轮不用摘要: {exc!r}")

    # 2.5) 跨会话记忆检索（T9.15）：只在用户话里有回溯指代时才跑，避免每条消息都查一遍。
    #      检索**强制按 user_id 过滤**，不会把别人的历史带进来。
    memory_context = ""
    if should_recall(request_text):
        try:
            memory_context = build_memory_context(
                db, user_id=user_id, query=request_text
            )
        except Exception as exc:  # noqa: BLE001
            # 检索失败不该影响正常回答：降级成「没有历史」继续走
            main_logger.warning(f"[记忆检索] 失败，本轮跳过: {exc!r}")

    # 2) system_prompt 为 None 时使用默认兜底提示词，确保链路始终可用。
    if system_prompt is None:
        system_prompt = "你是一个简洁、可靠的单Agent助手。优先直接回答问题，必要时结合检索信息。"

    prompt_messages: list[Any] = [("system", system_prompt)]
    if summary_text:
        # 更早内容的摘要放在历史之前，读起来就是「先看摘要，再看最近原文」。
        # 用现成的 SystemMessage 而不是模板字符串：摘要是**数据**不是模板，
        # 里面出现花括号会被 ChatPromptTemplate 当变量解析。
        prompt_messages.append(
            SystemMessage(
                content=(
                    "以下是本次会话更早内容的摘要，供你保持上下文连贯：\n\n"
                    + summary_text
                )
            )
        )
    prompt_messages.extend(
        [
            MessagesPlaceholder(variable_name="history"),
            # 本轮用户消息用消息占位符传入——带图片时它是多模态内容块，
            # 不是一段可以塞进 f-string 的文本
            MessagesPlaceholder(variable_name="user_messages"),
        ]
    )
    # 标记场景：文字对话算 chat（按轮数配额），语音面试在建立连接时已标成 voice，
    # 这里用 ensure_scene 兜底，不会把 voice 覆盖回 chat。
    ensure_scene(SCENE_CHAT)
    chain = ChatPromptTemplate.from_messages(prompt_messages) | get_chat_model(
        provider=provider
    )

    def chat_node(state: ChatGraphState) -> dict[str, Any]:
        """图的唯一节点：跑一遍「提示词 → 模型」，并把回复追加进状态历史。"""
        # 这里用 invoke 即可：LangGraph 的 stream_mode="messages" 会从模型回调里抽出 token 流。
        message = chain.invoke(
            {
                "history": state.get("history", []),
                "user_messages": state.get("user_messages", []),
            }
        )
        return {"history": [*state.get("history", []), message]}

    graph = StateGraph(ChatGraphState)
    graph.add_node("chat", chat_node)
    graph.add_edge(START, "chat")
    graph.add_edge("chat", END)

    # 3) search_result 实时检索补充外部知识，local_kb 作为本地知识备用。
    #    这两个变量内置提示词并不引用，只有自定义模板才可能用到。其中：
    #    - local_kb 是常量字典，代价为零，直接给出；
    #    - search_result 每次都要打一次外网检索，所以只在提示词真的引用了
    #      {search_result} 时才去取，避免每条消息白白增加一次网络延迟与失败面。
    needs_search = bool(system_prompt) and "{search_result}" in system_prompt
    stream_inputs: dict[str, Any] = {
        "history": history.messages,
        "user_messages": [
            _build_user_message(
                request_text, attachment_text, attachment_images or [], memory_context
            )
        ],
        "local_kb": {
            "Python": "基础语法、循环、函数、列表字典、文件操作、异常处理",
            "Java": "面向对象、集合、IO、多线程、Spring基础",
            "前端": "HTML/CSS、JS DOM、Vue、Ajax、响应式布局"
        },
        "search_result": get_latest_knowledge(request_text) if needs_search else "",
    }
    return graph.compile(), stream_inputs


def inject_user_info_to_template(
    template_content: str, # 参数1：完整的模板内容（含占位符）
    user_info_dict: dict,# 参数2：用户信息字典（格式化后的）
) -> str:
    """第三层：执行提示词注入 - 替换模板中的占位符为用户信息。"""
    prompt_content = template_content
    
    # 遍历字典的每个键值对
    for key, value in user_info_dict.items():
        # 构造占位符：{target_job}
        placeholder = "{" + key + "}"
        # 检查占位符是否存在
        if placeholder in prompt_content:
            # 替换占位符
            prompt_content = prompt_content.replace(placeholder, str(value))
    
    return prompt_content # 返回替换完成的提示词


def validate_user_info(user_info_dict: dict) -> dict:
    """第一层：验证 - 检查用户信息的有效性和安全性。"""
    FORBIDDEN_KEYWORDS = ["<script", "javascript:", "onclick", "prompt(", "eval("]
    MAX_LENGTH = {
        "target_job": 128,
        "years_experience": 64,
        "target_level": 32,
    }
    
    validated = {}
    for key, value in user_info_dict.items():
        if value is None:
            validated[key] = ""
            continue
        
        value_str = str(value)
        
        if key in MAX_LENGTH:
            max_len = MAX_LENGTH[key]
            if len(value_str) > max_len:
                value_str = value_str[:max_len]
        
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword.lower() in value_str.lower():
                raise ValueError(f"用户信息包含禁用内容: {keyword}")
        
        validated[key] = value_str
    
    return validated


def build_personalized_prompt(
    db: Session,
    user_id: int,
    agent_name: str,
    scene: str,
) -> Optional[str]:
    """构建个性化提示词 - 完整的三层处理流程。

    流程：验证 → 格式化（**按场景裁剪**，T9.7）→ 注入 → 追加本场景关注点。

    为什么要在末尾追加一句「关注点」：模板只能声明「有哪些背景可用」，
    没法表达「这个场景该重点参考哪几条」。这句由注入层按 scene 补，
    好处是**不用改任何模板**——模板一旦 seed 进库就有版本，改一次要走
    `--force` 出一版新的，成本比在这里追加一句话高得多。
    """
    try:
        user_info = UserProfileService.get_profile_dict(db, user_id)
        validated_info = validate_user_info(user_info)
        formatted_info = UserProfileService.format_profile_for_injection(
            validated_info, scene=scene
        )
        
        full_prompt = prompt_template_manager.get_full_prompt(agent_name, scene, db)
        if not full_prompt:
            return None
        
        personalized_prompt = inject_user_info_to_template(full_prompt, formatted_info)

        rule = get_injection_rule(scene)
        if rule.focus:
            personalized_prompt = f"{personalized_prompt}\n\n本场景的关注点：{rule.focus}"

        # L2 答题方法（T9.12）：只在「怎么答」有意义的场景注入。
        # 用追加而不是模板占位符，理由同上——模板改一次要升版本，而这块是场景策略。
        methods = user_info.get("answer_methods") or []
        if rule.include_methods and methods:
            personalized_prompt = (
                f"{personalized_prompt}\n\n"
                "该用户在答题方法上的已知问题（点评时请结合这些**具体指出**，"
                "不要泛泛地说「表达要更好」）：\n"
                + "\n".join(f"- {item}" for item in methods)
            )
        
        log_personalized_prompt_generated(personalized_prompt, user_id, agent_name, scene)
        
        return personalized_prompt
        
    except Exception as e:
        raise RuntimeError(f"构建个性化提示词失败: {e}")
