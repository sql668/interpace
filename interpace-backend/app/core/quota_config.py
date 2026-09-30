"""演示环境配额配置：从 JSON 文件读取，支持热重载（对应 T12.4）。

为什么单独放一个文件而不是塞进 `.env`：

1. **配额项会越来越多**（每 IP 的 token / 轮数 / 出题 / 复盘 / 语音分钟、每用户的上限、
   全局预算、降本开关），混在 `.env` 里会把真正的环境配置淹没；
2. `.env` 是**扁平的键值对**，表达不了「per_ip / global / cost_reduction」这种分组，
   而分组能让改配置的人一眼看懂这一项在管什么；
3. 用 **JSON 而不是 YAML**：`PyYAML` 目前只是其他库带进来的传递依赖，
   为它写配置等于依赖一个我们没声明的包（哪天上游去掉就会崩）。JSON 是标准库，零风险。

热重载的做法：每次读取先 `os.stat` 比 mtime，**改完保存最多 `RELOAD_INTERVAL_SECONDS`
秒生效，不需要重启服务**。

**改坏了不会挂**：解析或校验失败时保留上一次有效的配置并打 ERROR 日志。
这是刻意的——演示环境的价值在于"一直能访问"，配置文件里少个逗号不该让整站 500。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.logging_config import main_logger

# 配置文件默认位置：项目根/config/demo_limits.json
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "demo_limits.json"

# 检查频率：每次读取配额都会做一次 os.stat（很轻），命中改动才真正解析文件。
RELOAD_INTERVAL_SECONDS = 5.0


def _environments(data: dict[str, Any]) -> tuple[str, ...]:
    """解析 `environments` 列表；缺省只对 demo 生效。"""
    raw = data.get("environments", ["demo"])
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"environments 必须是非空数组，当前值：{raw!r}")
    return tuple(str(item).strip() for item in raw if str(item).strip())


@dataclass(frozen=True)
class PerIpLimits:
    """按 IP 的限制。token 是累计总量，其余按天。"""

    token_quota: int
    turns_per_day: int
    quizzes_per_day: int
    evaluations_per_day: int
    voice_minutes_per_day: int


@dataclass(frozen=True)
class PerUserLimits:
    """按账号的限制。"""

    max_sessions: int
    max_notes: int
    max_turns_per_session: int


@dataclass(frozen=True)
class InterviewLimits:
    """模拟面试的时长限制。"""

    max_minutes: int


@dataclass(frozen=True)
class GlobalLimits:
    """全局兜底预算。"""

    daily_token_budget: int
    daily_call_budget: int


@dataclass(frozen=True)
class CostReduction:
    """演示环境的降本开关。"""

    disable_background_extraction: bool
    disable_voice_interview: bool
    disable_file_upload: bool
    max_tokens: int


@dataclass(frozen=True)
class Notice:
    """给用户看的文案。"""

    banner_text: str
    rejected_message: str
    interview_timeout_message: str


@dataclass(frozen=True)
class DemoLimits:
    """演示环境配额的完整快照（不可变，读取时一次性拿到，避免中途被换掉）。"""

    enabled: bool
    environments: tuple[str, ...]
    per_ip: PerIpLimits
    per_user: PerUserLimits
    interview: InterviewLimits
    global_limits: GlobalLimits
    cost_reduction: CostReduction
    notice: Notice

    def applies_to_env(self, app_env: str) -> bool:
        """该环境是否受这套配额约束。

        只有 `enabled=true` **且**当前环境在 `environments` 列表里才算数。
        两段判断缺一不可：只有 `enabled` 会让开发机也被配额卡住、
        后台抽取被意外关掉；只有环境名则失去了"一键关掉"的开关。
        """
        return self.enabled and app_env in self.environments

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DemoLimits":
        """从解析后的 JSON 构造；缺项用安全默认值补齐，类型错误直接抛 ValueError。"""
        per_ip = data.get("per_ip") or {}
        per_user = data.get("per_user") or {}
        interview = data.get("interview") or {}
        global_limits = data.get("global") or {}
        reduction = data.get("cost_reduction") or {}
        notice = data.get("notice") or {}

        def _int(source: dict[str, Any], key: str, default: int) -> int:
            raw = source.get(key, default)
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} 必须是整数，当前值：{raw!r}") from exc
            if value < 0:
                raise ValueError(f"{key} 不能为负数，当前值：{value}")
            return value

        def _bool(source: dict[str, Any], key: str, default: bool) -> bool:
            raw = source.get(key, default)
            if not isinstance(raw, bool):
                raise ValueError(f"{key} 必须是 true 或 false，当前值：{raw!r}")
            return raw

        def _text(source: dict[str, Any], key: str, default: str) -> str:
            raw = source.get(key, default)
            return str(raw) if raw is not None else default

        return cls(
            enabled=_bool(data, "enabled", False),
            environments=_environments(data),
            per_ip=PerIpLimits(
                token_quota=_int(per_ip, "token_quota", 3_000_000),
                turns_per_day=_int(per_ip, "turns_per_day", 10),
                quizzes_per_day=_int(per_ip, "quizzes_per_day", 2),
                evaluations_per_day=_int(per_ip, "evaluations_per_day", 1),
                voice_minutes_per_day=_int(per_ip, "voice_minutes_per_day", 3),
            ),
            per_user=PerUserLimits(
                max_sessions=_int(per_user, "max_sessions", 3),
                max_notes=_int(per_user, "max_notes", 10),
                max_turns_per_session=_int(per_user, "max_turns_per_session", 5),
            ),
            interview=InterviewLimits(
                max_minutes=_int(interview, "max_minutes", 0),
            ),
            global_limits=GlobalLimits(
                daily_token_budget=_int(global_limits, "daily_token_budget", 500_000),
                daily_call_budget=_int(global_limits, "daily_call_budget", 150),
            ),
            cost_reduction=CostReduction(
                disable_background_extraction=_bool(
                    reduction, "disable_background_extraction", False
                ),
                disable_voice_interview=_bool(reduction, "disable_voice_interview", False),
                disable_file_upload=_bool(reduction, "disable_file_upload", False),
                max_tokens=_int(reduction, "max_tokens", 1024),
            ),
            notice=Notice(
                banner_text=_text(notice, "banner_text", ""),
                rejected_message=_text(
                    notice,
                    "rejected_message",
                    "演示环境的体验额度已用完。",
                ),
                interview_timeout_message=_text(
                    notice,
                    "interview_timeout_message",
                    "本场模拟面试已达 {minutes} 分钟上限，已自动结束。",
                ),
            ),
        )


# 保守的默认值：配置文件读不到时用这一份（且此时 enabled=False，也就是"不限制"）。
# 刻意**不是**"读不到就全禁"——配置读取失败多半是部署问题，不应该把所有用户挡在门外。
_FALLBACK_LIMITS = DemoLimits.from_dict({})


class DemoLimitsLoader:
    """带 mtime 热重载的配置加载器。"""

    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._limits = _FALLBACK_LIMITS
        self._mtime: float | None = None
        self._last_check = 0.0
        self._last_error: str | None = None
        self._loaded_once = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def last_error(self) -> str | None:
        """最近一次加载失败的原因（成功则清空），供 /health 与排查使用。"""
        return self._last_error

    def current(self) -> DemoLimits:
        """取当前生效的配额快照；必要时先尝试重载。"""
        self._maybe_reload()
        return self._limits

    def reload(self, *, force: bool = False) -> DemoLimits:
        """立即（重新）读取配置文件。`force=True` 时忽略 mtime 判断。"""
        with self._lock:
            self._load_locked(force=force)
            return self._limits

    def _maybe_reload(self) -> None:
        now = time.monotonic()
        # 未加载过、或距上次检查超过间隔，才去看文件状态。
        if self._loaded_once and (now - self._last_check) < RELOAD_INTERVAL_SECONDS:
            return
        with self._lock:
            if self._loaded_once and (now - self._last_check) < RELOAD_INTERVAL_SECONDS:
                return
            self._last_check = now
            self._load_locked(force=False)

    def _load_locked(self, *, force: bool) -> None:
        self._last_check = time.monotonic()
        try:
            mtime = self._path.stat().st_mtime
        except FileNotFoundError:
            self._loaded_once = True
            if force or self._mtime is not None:
                self._record_failure(f"配置文件不存在：{self._path}")
            self._mtime = None
            return
        except OSError as exc:  # 权限之类的问题
            self._loaded_once = True
            self._record_failure(f"读取配置失败：{exc}")
            return

        if not force and self._loaded_once and self._mtime == mtime:
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            limits = DemoLimits.from_dict(json.loads(raw))
        except Exception as exc:  # noqa: BLE001 —— 配置错误绝不能让服务挂掉
            self._loaded_once = True
            self._record_failure(f"解析配置失败：{exc}")
            return

        self._loaded_once = True
        first_load = self._mtime is None
        self._mtime = mtime
        self._limits = limits
        self._last_error = None
        if first_load or force:
            main_logger.info(
                f"[演示配额] 已加载 {self._path}：enabled={limits.enabled} "
                f"每IP总量={limits.per_ip.token_quota} token"
            )
        else:
            main_logger.info(f"[演示配额] 配置已热更新：{self._path}")

    def _record_failure(self, message: str) -> None:
        # 只在错误内容变化时打日志，避免每 5 秒刷一条重复 ERROR。
        if self._last_error != message:
            main_logger.error(f"[演示配额] {message}（继续沿用上一份有效配置）")
        self._last_error = message


# 进程级单例
demo_limits_loader = DemoLimitsLoader()
