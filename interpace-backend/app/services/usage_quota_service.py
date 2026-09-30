"""用量记账与配额校验（T12.3 / T12.4）。

这一层是"演示环境别被刷爆"的执行者，规则来自 `config/demo_limits.json`（可热改）。

## 三个刻意的设计

1. **在模型调用这一层卡，不在接口入口卡。**
   一次用户提问可能触发多次模型调用（会话摘要压缩、画像抽取、出题后的评分……），
   按接口次数限流和 token 消耗不是一回事。全项目唯一的模型出口是
   `app/agent/llm.py:get_chat_model`，配额与记账都挂在那里。

2. **按 provider 返回的真实用量记账，不估算。**
   估算在中文场景误差极大，而且这个模型的推理过程也计费（实测输出 137 token
   里 133 是 reasoning），估算值完全对不上账单。

3. **先记账再放行下一轮，超额只拒绝"下一次调用"。**
   已经在跑的对话不会被中途掐断——用户看到的是"这次说完，再问就不行了"，
   比流到一半被切断的体验好得多，也避免落库逻辑走不完。

## 为什么不用聚合表

配额判断要在 `usage_records` 上做 SUM/COUNT。演示环境的数据量很小
（每天最多几百行），有 `(client_ip, created_at)` 与 `(created_at)` 两条索引足够。
等哪天明细表到几十万行、SUM 明显变慢，再加按天聚合表——现在加只是提前复杂化。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dt_time
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import main_logger
from app.core.quota_config import DemoLimits, demo_limits_loader
from app.core.settings import settings
from app.db.database import SessionLocal
from app.db.models import UsageRecord

# 会被「每日次数」限制的场景。其它场景（memory / summary 等后台调用）只累计 token，
# 不单独卡次数——它们本来就是被前台的对话与出题带出来的。
SCENE_CHAT = "chat"
SCENE_QUIZ = "quiz"
SCENE_EVALUATION = "evaluation"
SCENE_VOICE = "voice"
# 后台调用（用户看不见，但对尝鲜体验没贡献，演示环境可整体关掉）
SCENE_MEMORY = "memory"
SCENE_SUMMARY = "summary"
SCENE_RESUME = "resume"

DAILY_LIMITED_SCENES = (SCENE_CHAT, SCENE_QUIZ, SCENE_EVALUATION)


def day_start_ts(now: datetime | None = None) -> int:
    """返回"今天零点"的 Unix 秒。

    用服务器本地时区（容器里是 Asia/Shanghai）：演示环境的"每日"要对应用户感受到的一天，
    用 UTC 会让配额在北京时间早上 8 点才重置，用户会觉得莫名其妙。
    """
    current = now or datetime.now()
    return int(datetime.combine(date(current.year, current.month, current.day), dt_time.min).timestamp())


@dataclass(frozen=True)
class IpUsage:
    """某个 IP 的用量快照，用于配额判断与排查。"""

    tokens_total: int
    calls_today: int
    turns_today: int
    quizzes_today: int
    evaluations_today: int


@dataclass(frozen=True)
class GlobalUsage:
    """全局当日用量快照。"""

    tokens_today: int
    calls_today: int


class UsageQuotaService:
    """用量记账 + 配额校验。"""

    # ---------- 配置 ----------

    @staticmethod
    def limits() -> DemoLimits:
        """取当前生效的配额配置（内部会按 mtime 做热重载）。"""
        return demo_limits_loader.current()

    @staticmethod
    def is_enforced() -> bool:
        """当前环境是否受配额约束。

        两个条件都满足才算：配置里的总开关打开 **且** 当前 `APP_ENV` 在
        `environments` 列表里（默认只有 demo）。开发 / 测试 / 正式环境恒为 False。
        """
        return UsageQuotaService.limits().applies_to_env(settings.app_env)

    # ---------- 记账 ----------

    @staticmethod
    def record(
        *,
        client_ip: str,
        scene: str,
        provider: str = "",
        model: str = "",
        user_id: int | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
        db: Session | None = None,
    ) -> None:
        """写一条用量明细。

        `total_tokens` 为 0 但确实发生了调用时也会写一行（`calls` 计数用得上），
        并打一条 warning——provider 哪天不再返回用量，配额会静默退化，
        必须让它在日志里叫出来。
        """
        if total_tokens <= 0:
            main_logger.warning(
                f"[用量记账] 未拿到 token 用量：scene={scene} provider={provider} "
                f"model={model} ip={client_ip or '-'}（配额将只按调用次数生效）"
            )

        own_session = db is None
        session = db or SessionLocal()
        try:
            row = UsageRecord(
                user_id=user_id,
                client_ip=client_ip or "",
                app_env=settings.app_env,
                scene=scene or "",
                provider=provider or "",
                model=model or "",
                prompt_tokens=max(0, prompt_tokens),
                completion_tokens=max(0, completion_tokens),
                reasoning_tokens=max(0, reasoning_tokens),
                total_tokens=max(0, total_tokens),
            )
            session.add(row)
            session.commit()
        except Exception:  # noqa: BLE001 —— 记账失败不能影响用户的正常使用
            session.rollback()
            main_logger.exception("[用量记账] 写入失败（不影响本次调用）")
        finally:
            if own_session:
                session.close()

    # ---------- 查询 ----------

    @staticmethod
    def snapshot_for_ip(client_ip: str, *, db: Session | None = None) -> IpUsage:
        """取某个 IP 的累计 token 与当日各场景次数。"""
        own_session = db is None
        session = db or SessionLocal()
        try:
            total = session.scalar(
                select(func.coalesce(func.sum(UsageRecord.total_tokens), 0)).where(
                    UsageRecord.client_ip == client_ip
                )
            )
            start = day_start_ts()
            rows = session.execute(
                select(UsageRecord.scene, func.count())
                .where(
                    UsageRecord.client_ip == client_ip,
                    UsageRecord.created_at >= start,
                )
                .group_by(UsageRecord.scene)
            ).all()
            by_scene = {scene: count for scene, count in rows}
            return IpUsage(
                tokens_total=int(total or 0),
                calls_today=sum(by_scene.values()),
                turns_today=by_scene.get(SCENE_CHAT, 0) + by_scene.get(SCENE_VOICE, 0),
                quizzes_today=by_scene.get(SCENE_QUIZ, 0),
                evaluations_today=by_scene.get(SCENE_EVALUATION, 0),
            )
        finally:
            if own_session:
                session.close()

    @staticmethod
    def snapshot_global(*, db: Session | None = None) -> GlobalUsage:
        """取全局当日用量（所有 IP 合计）。"""
        own_session = db is None
        session = db or SessionLocal()
        try:
            start = day_start_ts()
            row = session.execute(
                select(
                    func.coalesce(func.sum(UsageRecord.total_tokens), 0),
                    func.count(),
                ).where(UsageRecord.created_at >= start)
            ).one()
            return GlobalUsage(tokens_today=int(row[0] or 0), calls_today=int(row[1] or 0))
        finally:
            if own_session:
                session.close()

    # ---------- 校验 ----------

    @staticmethod
    def check_before_call(
        *, scene: str, client_ip: str, db: Session | None = None
    ) -> None:
        """模型调用前的准入检查；超额直接抛 429。

        检查顺序是刻意从"最容易解释"到"最细"：全局熔断 → 单 IP 累计上限 →
        单 IP 当日次数。这样用户看到的拒绝理由是最外层的那条，不会出现
        "同样是超额，有时说次数用完、有时说总额用完"的混乱。
        """
        limits = UsageQuotaService.limits()
        if not limits.applies_to_env(settings.app_env):
            return

        own_session = db is None
        session = db or SessionLocal()
        try:
            global_usage = UsageQuotaService.snapshot_global(db=session)
            if (
                global_usage.tokens_today >= limits.global_limits.daily_token_budget
                or global_usage.calls_today >= limits.global_limits.daily_call_budget
            ):
                UsageQuotaService._reject(
                    reason="global_budget",
                    detail={
                        "tokens_today": global_usage.tokens_today,
                        "token_budget": limits.global_limits.daily_token_budget,
                        "calls_today": global_usage.calls_today,
                        "call_budget": limits.global_limits.daily_call_budget,
                    },
                    message=limits.notice.rejected_message,
                )

            usage = UsageQuotaService.snapshot_for_ip(client_ip, db=session)
            if usage.tokens_total >= limits.per_ip.token_quota:
                UsageQuotaService._reject(
                    reason="ip_token_quota",
                    detail={
                        "tokens_total": usage.tokens_total,
                        "token_quota": limits.per_ip.token_quota,
                    },
                    message=limits.notice.rejected_message,
                )

            per_scene_limit = {
                SCENE_CHAT: (usage.turns_today, limits.per_ip.turns_per_day),
                SCENE_QUIZ: (usage.quizzes_today, limits.per_ip.quizzes_per_day),
                SCENE_EVALUATION: (
                    usage.evaluations_today,
                    limits.per_ip.evaluations_per_day,
                ),
            }
            if scene in per_scene_limit:
                used, allowed = per_scene_limit[scene]
                if used >= allowed:
                    UsageQuotaService._reject(
                        reason="ip_daily_quota",
                        detail={"scene": scene, "used": used, "allowed": allowed},
                        message=limits.notice.rejected_message,
                    )
        finally:
            if own_session:
                session.close()

    @staticmethod
    def _reject(*, reason: str, detail: dict, message: str) -> None:
        # 延迟导入：core.exceptions 与本模块没有循环依赖，但保持 import 区清爽。
        from app.core import raise_error

        main_logger.warning(f"[演示配额] 拒绝一次调用：reason={reason} detail={detail}")
        raise_error(
            code=429,
            message=message or "演示环境的体验额度已用完。",
            detail={"reason": reason, **detail},
        )

    # ---------- 降本开关（给其它服务判断） ----------

    @staticmethod
    def background_extraction_disabled() -> bool:
        """演示环境是否关掉了"用户看不见的额外模型调用"。

        覆盖：简历画像抽取、记忆抽取与合并、会话摘要压缩。这三件事都在后台额外烧 token，
        但对"尝鲜体验"几乎没有贡献。
        """
        limits = UsageQuotaService.limits()
        return bool(
            limits.applies_to_env(settings.app_env)
            and limits.cost_reduction.disable_background_extraction
        )

    @staticmethod
    def voice_interview_disabled() -> bool:
        """演示环境是否关掉了语音面试（T12.4）。

        这个开关有**两个**消费方，读的是同一份配置：
        - 前端通过 `GET /config/runtime` 拿到它，决定要不要显示「语音面试」按钮；
        - 后端的 WebSocket 路由拿它决定要不要接受连接。

        两边都判是刻意的：按钮只是界面，绕过界面直接连上来的请求才是真风险
        （语音是双计费，最贵的一条链路）。
        """
        limits = UsageQuotaService.limits()
        return bool(
            limits.applies_to_env(settings.app_env)
            and limits.cost_reduction.disable_voice_interview
        )

    @staticmethod
    def file_upload_disabled() -> bool:
        """演示环境是否关掉了附件上传（T12.5）。

        同 `voice_interview_disabled`：前端据它隐藏「+ 附件」入口，后端上传接口也判一次。
        PDF / 图片解析出的全文会整段进上下文，一次能顶几十轮对话，是性价比最高的一道闸。
        """
        limits = UsageQuotaService.limits()
        return bool(
            limits.applies_to_env(settings.app_env)
            and limits.cost_reduction.disable_file_upload
        )

    @staticmethod
    def runtime_snapshot() -> dict:
        """当前环境对本端生效的能力与提示，供前端一次性拉取。

        只暴露**真实生效**的项，不做"先占个位以后再用"——
        前端照着它做界面，就不能有"字段有值但后端其实没判"的情况。

        配额数值也一并返回（`limits`）：首页要如实写明演示环境的限制，
        如果前端自己抄一份数字，改配置后就会变成骗人的。
        """
        limits = UsageQuotaService.limits()
        enforced = UsageQuotaService.is_enforced()
        return {
            "app_env": settings.app_env,
            "quota_enforced": enforced,
            "features": {
                "voice_interview": not UsageQuotaService.voice_interview_disabled(),
                "file_upload": not UsageQuotaService.file_upload_disabled(),
            },
            "interview_max_minutes": UsageQuotaService.interview_max_minutes(),
            "notice": {"banner_text": limits.notice.banner_text},
            "limits": (
                {
                    "tokens_per_ip": limits.per_ip.token_quota,
                    "turns_per_day": limits.per_ip.turns_per_day,
                    "quizzes_per_day": limits.per_ip.quizzes_per_day,
                    "evaluations_per_day": limits.per_ip.evaluations_per_day,
                    "voice_minutes_per_day": limits.per_ip.voice_minutes_per_day,
                    "max_turns_per_session": limits.per_user.max_turns_per_session,
                    "max_sessions": limits.per_user.max_sessions,
                    "max_notes": limits.per_user.max_notes,
                }
                if enforced
                else None
            ),
        }

    @staticmethod
    def effective_max_tokens(configured: int) -> int:
        """演示环境把单次输出上限压到配置的值；其它环境原样返回。"""
        limits = UsageQuotaService.limits()
        if not limits.applies_to_env(settings.app_env):
            return configured
        cap = limits.cost_reduction.max_tokens
        if cap <= 0:
            return configured
        return min(configured, cap)

    # ---------- 模拟面试时长限制 ----------

    @staticmethod
    def interview_max_minutes() -> int:
        """单场模拟面试的时长上限（分钟）；0 表示不限。"""
        limits = UsageQuotaService.limits()
        if not limits.applies_to_env(settings.app_env):
            return 0
        return max(0, limits.interview.max_minutes)

    @staticmethod
    def interview_remaining_seconds(started_at: int | None) -> int | None:
        """给定面试开始时间，返回本场还剩多少秒。

        - 返回 `None`：不限制时长（非演示环境，或配置为 0）；
        - 返回 `<= 0`：**已经超时**（保留具体负值，日志里能看到超了多少）。

        `started_at` 用的是面试记录的创建时间，所以语音与文字两种形式共用同一个时钟，
        同一场面试里来回切换也不会各算一份。
        """
        max_minutes = UsageQuotaService.interview_max_minutes()
        if max_minutes <= 0:
            return None
        try:
            started = int(started_at or 0)
        except (TypeError, ValueError):
            started = 0
        # 拿不到创建时间（例如面试还没建立）时按"刚开始"处理，给足配额。
        if started <= 0:
            return max_minutes * 60
        return max_minutes * 60 - (int(time.time()) - started)

    @staticmethod
    def interview_timeout_message(minutes: int | None = None) -> str:
        """超时提示文案（支持配置里的 {minutes} 占位）。"""
        limits = UsageQuotaService.limits()
        actual = minutes if minutes is not None else UsageQuotaService.interview_max_minutes()
        template = limits.notice.interview_timeout_message
        try:
            return template.format(minutes=actual)
        except (KeyError, IndexError, ValueError):
            # 配置里写错了占位符也不能因此报错——降级成去掉占位符的原文。
            return template
