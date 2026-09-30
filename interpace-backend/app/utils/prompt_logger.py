"""提示词系统的集中日志输出管理。

统一走 loguru（`main_logger`），不再直接 `print`：

- 关键统计用 INFO，方便一眼看出走了哪个 Agent / 场景；
- **完整提示词正文用 DEBUG**，避免默认级别把用户画像、模板全文这类内容
  未经管理地打到标准输出和日志文件里。
"""

from app.core.logging_config import main_logger


def log_redis_status(use_redis: bool, error: str | None = None) -> None:
    """记录 Redis 连接状态。"""
    if use_redis:
        main_logger.info("[提示词系统] Redis 已连接，使用缓存")
    else:
        main_logger.warning(f"[提示词系统] Redis 不可用，将使用数据库查询: {error}")


def log_personalized_prompt_generated(
    prompt: str, user_id: int, agent_name: str, scene: str
) -> None:
    """记录个性化提示词生成情况；正文只在 DEBUG 级别输出。"""
    main_logger.info(
        f"[个性化提示词] user_id={user_id} agent={agent_name} "
        f"scene={scene} 长度={len(prompt)} 字符"
    )
    main_logger.debug(f"[个性化提示词正文]\n{prompt}")


def log_chain_ready(
    user_id: int,
    session_id: int,
    agent_name: str,
    scene: str,
    provider: str,
    prompt_length: int,
) -> None:
    """记录链路就绪的关键统计。"""
    main_logger.info(
        f"[链路就绪] user_id={user_id} session_id={session_id} agent={agent_name} "
        f"scene={scene} provider={provider} 提示词长度={prompt_length} 字符"
    )
