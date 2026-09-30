"""T12.1 / T12.3 / T12.4 回归测试：多环境归一、用量记账、演示配额拦截。

这一组用例盯的是"演示环境别被刷爆"这条需求里最容易默默失效的几个点：

- 配置文件改完不生效 / 改坏了把服务带崩；
- 配额在开发环境也被打开（自己把自己卡住）；
- 记账拿不到 token 数（看着有功能，其实配额永远不触发）；
- 按 IP 的额度能被"删号重建"或伪造请求头洗掉。

测试用的配额配置都是就地构造的，不动 `config/demo_limits.json`。
"""

import json
from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from sqlalchemy import delete

from api_helpers import create_session
from app.agent import prompt_layer
from app.agent.usage_callback import UsageRecordingCallback
from app.core import AppException
from app.core import client_ip as client_ip_module
from app.core.client_ip import UNKNOWN_CLIENT_IP, resolve_client_ip_from_headers
from app.core.quota_config import DemoLimits, DemoLimitsLoader
from app.core.request_context import get_request_context
from app.core.settings import VALID_APP_ENVS, _normalize_app_env
from app.db.database import SessionLocal
from app.db.models import UsageRecord
from app.services.usage_quota_service import SCENE_CHAT, SCENE_QUIZ, UsageQuotaService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

# 测试用的假 IP：用 203.0.113.0/24（RFC 5737 文档专用段），不会和真实流量撞上。
TEST_IP_A = "203.0.113.10"
TEST_IP_B = "203.0.113.11"


@pytest.fixture(autouse=True)
def clean_usage_records() -> None:
    """用例前后都清掉测试 IP 的账本，避免互相污染与给开发库留垃圾。"""
    _purge_usage()
    yield
    _purge_usage()


def _purge_usage() -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(UsageRecord).where(
                UsageRecord.client_ip.in_([TEST_IP_A, TEST_IP_B, UNKNOWN_CLIENT_IP])
            )
        )
        db.commit()
    finally:
        db.close()


def _limits(overrides: dict[str, Any] | None = None, **kwargs: Any) -> DemoLimits:
    """构造一份"只对当前测试环境生效"的配额，值按需覆盖。"""
    data: dict[str, Any] = {
        # development 也纳入，这样测试不必真的切到 demo 环境（settings 是导入期单例）。
        "enabled": True,
        "environments": ["development"],
        "per_ip": {
            "token_quota": 1000,
            "turns_per_day": 10,
            "quizzes_per_day": 2,
            "evaluations_per_day": 1,
            "voice_minutes_per_day": 3,
        },
        "per_user": {
            "max_sessions": 3,
            "max_notes": 10,
            "max_turns_per_session": 5,
        },
        "global": {"daily_token_budget": 100000, "daily_call_budget": 1000},
        "cost_reduction": {
            "disable_background_extraction": False,
            "disable_voice_interview": False,
            "disable_file_upload": False,
            "max_tokens": 1024,
        },
        "notice": {"banner_text": "演示环境", "rejected_message": "演示额度已用完"},
    }
    # `global` 是 Python 关键字，写不成关键字参数，所以额外支持传一个字典。
    merged_overrides = {**(overrides or {}), **kwargs}
    for key, value in merged_overrides.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return DemoLimits.from_dict(data)


@pytest.fixture
def active_limits(monkeypatch: pytest.MonkeyPatch):
    """把配额配置替换成指定的一份（默认可用的那套）。"""

    def _apply(limits: DemoLimits) -> None:
        monkeypatch.setattr(
            UsageQuotaService, "limits", staticmethod(lambda: limits)
        )

    _apply(_limits())
    return _apply


# ---------------- 多环境归一（T12.1） ----------------


def test_app_env_accepts_four_environments() -> None:
    """四套环境都能识别，简写也认。"""
    assert set(VALID_APP_ENVS) == {"development", "demo", "test", "production"}
    assert _normalize_app_env("demo") == "demo"
    assert _normalize_app_env("DEMO") == "demo"
    assert _normalize_app_env("test") == "test"
    assert _normalize_app_env("prod") == "production"
    assert _normalize_app_env("dev") == "development"
    assert _normalize_app_env(None) == "development"


def test_app_env_typo_fails_fast() -> None:
    """环境名写错必须启动即失败。

    原来任何不认识的值都会被静默归到 development——`APP_ENV=demoo` 会安静地
    按开发环境跑（配额全不生效），这是演示环境最危险的一类错。
    """
    with pytest.raises(RuntimeError) as exc:
        _normalize_app_env("demoo")
    assert "demoo" in str(exc.value)
    assert "demo" in str(exc.value)  # 报错里要给出可选值


def test_limits_only_apply_to_configured_environments() -> None:
    """配额只对配置里列出的环境生效，开关关掉后一律不生效。"""
    limits = _limits(environments=["demo"])
    assert limits.applies_to_env("demo") is True
    assert limits.applies_to_env("development") is False
    assert limits.applies_to_env("production") is False

    disabled = _limits(enabled=False, environments=["demo"])
    assert disabled.applies_to_env("demo") is False


def test_dev_environment_not_blocked_by_demo_limits() -> None:
    """开发环境不受演示配额影响：后台抽取照常、输出上限不被压。

    这条是踩过的坑：配额配置一开始写成了无条件的 `enabled=true`，
    结果本地开发也被卡住、后台画像/记忆抽取被静默关掉。
    """
    # 当前测试进程的 APP_ENV 是 development，而配置只对 demo 生效。
    assert UsageQuotaService.is_enforced() is False
    assert UsageQuotaService.background_extraction_disabled() is False
    assert UsageQuotaService.effective_max_tokens(10240) == 10240


def test_demo_environment_flags_take_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    """切到演示环境后，降本开关与输出上限才生效。"""
    import app.services.usage_quota_service as service_module

    monkeypatch.setattr(
        UsageQuotaService, "limits", staticmethod(lambda: _limits(environments=["demo"]))
    )
    # settings 是 frozen dataclass，改不了属性；替换模块级引用即可（判断读的就是它）。
    class _FakeSettings:
        app_env = "demo"

    monkeypatch.setattr(service_module, "settings", _FakeSettings())
    assert UsageQuotaService.is_enforced() is True
    assert UsageQuotaService.background_extraction_disabled() is False  # 本用例没开这个开关
    assert UsageQuotaService.effective_max_tokens(10240) == 1024

    # 打开降本开关后，后台抽取也要被关掉
    monkeypatch.setattr(
        UsageQuotaService,
        "limits",
        staticmethod(
            lambda: _limits(
                environments=["demo"], cost_reduction={"disable_background_extraction": True}
            )
        ),
    )
    assert UsageQuotaService.background_extraction_disabled() is True


# ---------------- 配置热重载 ----------------


def _write_config(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_config_hot_reload(tmp_path: Path) -> None:
    """改文件后不需要重启：下一次读取就能拿到新值。"""
    path = tmp_path / "demo_limits.json"
    _write_config(path, {"enabled": True, "environments": ["demo"], "per_ip": {"token_quota": 100}})

    loader = DemoLimitsLoader(path)
    assert loader.current().per_ip.token_quota == 100

    _write_config(path, {"enabled": True, "environments": ["demo"], "per_ip": {"token_quota": 200}})
    # 同一秒内写入时 mtime 可能不变，先验证"强制重载"能拿到新值。
    assert loader.reload(force=True).per_ip.token_quota == 200

    # 再验证"只靠 mtime 发现变化"这条热更新路径确实生效（把 mtime 往前推）。
    import os
    import time as time_module

    _write_config(path, {"enabled": True, "environments": ["demo"], "per_ip": {"token_quota": 300}})
    future = time_module.time() + 60
    os.utime(path, (future, future))
    loader._last_check = 0.0  # 绕过 5 秒的检查间隔
    assert loader.current().per_ip.token_quota == 300


def test_broken_config_keeps_previous_limits(tmp_path: Path) -> None:
    """配置写坏时保留上一份有效配置，并把错误暴露出来——不能把整站带崩。"""
    path = tmp_path / "demo_limits.json"
    _write_config(path, {"enabled": True, "environments": ["demo"], "per_ip": {"token_quota": 500}})
    loader = DemoLimitsLoader(path)
    assert loader.current().per_ip.token_quota == 500
    assert loader.last_error is None

    path.write_text("{ 这不是合法 JSON", encoding="utf-8")
    still = loader.reload(force=True)
    assert still.per_ip.token_quota == 500, "写坏配置后必须沿用上一份有效配置"
    assert loader.last_error and "解析配置失败" in loader.last_error

    # 类型错误同样拦住（token_quota 必须是整数）
    _write_config(path, {"enabled": True, "per_ip": {"token_quota": "很多"}})
    loader.reload(force=True)
    assert loader.current().per_ip.token_quota == 500
    assert loader.last_error and "必须是整数" in loader.last_error


# ---------------- 真实 IP 解析（配额的前提） ----------------


def test_forwarded_for_cannot_be_spoofed(monkeypatch: pytest.MonkeyPatch) -> None:
    """伪造 `X-Forwarded-For` 不能改自己的配额身份。

    Nginx 用的是 `$proxy_add_x_forwarded_for`（保留客户端值、在末尾追加真实 IP），
    所以只有**最后一段**可信。原来取第一段，攻击者每个请求换一个假 IP 就能绕过限流。
    """
    monkeypatch.setattr(client_ip_module, "settings", _FakeTrustProxy(True))
    headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 203.0.113.99"}
    assert resolve_client_ip_from_headers(headers, "127.0.0.1") == "203.0.113.99"

    # X-Real-IP 由 Nginx 覆盖写入，优先级最高
    headers_with_real = {**headers, "x-real-ip": "198.51.100.7"}
    assert resolve_client_ip_from_headers(headers_with_real, "127.0.0.1") == "198.51.100.7"

    # 不信任代理头（默认）：直连地址说了算，伪造头一律忽略
    monkeypatch.setattr(client_ip_module, "settings", _FakeTrustProxy(False))
    assert resolve_client_ip_from_headers(headers_with_real, "127.0.0.1") == "127.0.0.1"


class _FakeTrustProxy:
    def __init__(self, trust: bool) -> None:
        self.trust_proxy_headers = trust


class _FakeSettings:
    """把"当前环境"换成 demo（settings 是 frozen dataclass，只能换模块级引用）。"""

    app_env = "demo"


# ---------------- 记账与配额 ----------------


def _record(ip: str, *, scene: str = SCENE_CHAT, tokens: int = 100) -> None:
    UsageQuotaService.record(
        client_ip=ip,
        scene=scene,
        provider="deepseek",
        model="deepseek-flash",
        prompt_tokens=tokens // 2,
        completion_tokens=tokens - tokens // 2,
        total_tokens=tokens,
    )


def test_record_and_snapshot() -> None:
    """记账能落库，快照能按 IP 与场景汇总。"""
    _record(TEST_IP_A, scene=SCENE_CHAT, tokens=120)
    _record(TEST_IP_A, scene=SCENE_QUIZ, tokens=80)

    usage = UsageQuotaService.snapshot_for_ip(TEST_IP_A)
    assert usage.tokens_total == 200
    assert usage.calls_today == 2
    assert usage.turns_today == 1
    assert usage.quizzes_today == 1

    # 另一个 IP 不受影响
    assert UsageQuotaService.snapshot_for_ip(TEST_IP_B).tokens_total == 0


def test_ip_token_quota_blocks(active_limits) -> None:
    """每 IP 累计 token 用完即拒——这是用户要求的硬天花板。"""
    active_limits(_limits(per_ip={"token_quota": 150}))
    _record(TEST_IP_A, tokens=100)
    UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_A)  # 还没超

    _record(TEST_IP_A, tokens=60)
    with pytest.raises(AppException) as exc:
        UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_A)
    assert exc.value.code == 429
    assert exc.value.detail["reason"] == "ip_token_quota"
    assert exc.value.detail["tokens_total"] == 160


def test_daily_turn_quota_blocks(active_limits) -> None:
    """按天的次数限制：用完当天的对话轮数就拒绝，与 token 是否耗尽无关。"""
    active_limits(_limits(per_ip={"turns_per_day": 2}))
    _record(TEST_IP_A)
    _record(TEST_IP_A)

    with pytest.raises(AppException) as exc:
        UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_A)
    assert exc.value.detail["reason"] == "ip_daily_quota"
    assert exc.value.detail["scene"] == SCENE_CHAT

    # 不同场景各有各的额度：对话满了不影响出题
    UsageQuotaService.check_before_call(scene=SCENE_QUIZ, client_ip=TEST_IP_A)


def test_global_budget_stops_everyone(active_limits) -> None:
    """全局熔断：按 IP 限流挡不住"很多人各用一点"，这一层才护住钱包。"""
    active_limits(_limits({"global": {"daily_call_budget": 1, "daily_token_budget": 10**9}}))
    _record(TEST_IP_A)

    with pytest.raises(AppException) as exc:
        UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_B)
    assert exc.value.detail["reason"] == "global_budget"


def test_quota_is_isolated_per_ip(active_limits) -> None:
    """一个 IP 用完不影响另一个 IP——否则演示站会被第一个访问者锁死。"""
    active_limits(_limits(per_ip={"token_quota": 50}))
    _record(TEST_IP_A, tokens=60)

    with pytest.raises(AppException):
        UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_A)
    UsageQuotaService.check_before_call(scene=SCENE_CHAT, client_ip=TEST_IP_B)


def test_unknown_ip_shares_one_quota() -> None:
    """解析不出 IP 时全部算作同一份额度（保守），而不是各自放行。"""
    assert resolve_client_ip_from_headers({}, None) == UNKNOWN_CLIENT_IP


# ---------------- 模型出口的接线 ----------------


def test_llm_exit_attaches_usage_callback() -> None:
    """模型出口必须挂上记账回调，否则配额永远拿不到用量。"""
    from app.agent.llm import get_chat_model

    model = get_chat_model(provider="deepseek")
    callbacks = model.callbacks or []
    assert any(
        isinstance(cb, UsageRecordingCallback) for cb in callbacks
    ), "get_chat_model 必须挂 UsageRecordingCallback"
    assert model.stream_usage is True, "不开 stream_usage 流式请求拿不到用量"


def test_usage_callback_writes_real_tokens() -> None:
    """回调把 provider 返回的真实 token 数写进账本（含推理 token）。"""
    callback = UsageRecordingCallback(
        scene=SCENE_CHAT,
        client_ip=TEST_IP_A,
        user_id=None,
        provider="deepseek",
        model="deepseek-flash",
    )
    message = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": 35,
            "output_tokens": 137,
            "total_tokens": 172,
            "output_token_details": {"reasoning": 133},
        },
    )
    callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))

    usage = UsageQuotaService.snapshot_for_ip(TEST_IP_A)
    assert usage.tokens_total == 172
    assert usage.turns_today == 1

    db = SessionLocal()
    try:
        row = (
            db.query(UsageRecord).filter(UsageRecord.client_ip == TEST_IP_A).one()
        )
        # 推理 token 要单独留档：它占了这个模型输出的大头，也是成本的主要来源。
        assert row.reasoning_tokens == 133
        assert row.completion_tokens == 137
        assert row.app_env  # 记下调用发生在哪套环境
    finally:
        db.close()


def test_model_call_blocked_when_over_quota(active_limits) -> None:
    """超额时连模型实例都不该创建：检查发生在建模型之前。"""
    from app.agent.llm import get_chat_model

    active_limits(_limits(per_ip={"token_quota": 10}))
    _record(TEST_IP_A, tokens=20)

    from app.core.request_context import set_request_context, reset_request_context

    token = set_request_context(client_ip=TEST_IP_A, scene=SCENE_CHAT)
    try:
        with pytest.raises(AppException) as exc:
            get_chat_model(provider="deepseek")
        assert exc.value.code == 429
    finally:
        reset_request_context(token)


# ---------------- 运行时能力开关 ----------------


@pytest.mark.anyio
async def test_runtime_config_endpoint_defaults(async_client: AsyncClient) -> None:
    """`/config/runtime` 要如实反映当前环境：开发环境不限制、语音开放。"""
    response = await async_client.get("/config/runtime")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["app_env"] == "development"
    assert body["quota_enforced"] is False
    assert body["features"]["voice_interview"] is True
    assert body["features"]["file_upload"] is True
    assert body["interview_max_minutes"] == 0
    # 没启用配额时必须显式给 null，前端据此显示"当前环境没有配额限制"
    assert body["limits"] is None


@pytest.mark.anyio
async def test_runtime_config_reports_demo_switches(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """演示环境下前端要能拿到"语音面试已关闭"。

    这个字段是「演示环境不显示语音面试按钮」的唯一依据，
    所以必须有用例盯着它，而不是靠前端自己猜环境。
    """
    import app.services.usage_quota_service as service_module

    monkeypatch.setattr(service_module, "settings", _FakeSettings())
    monkeypatch.setattr(
        UsageQuotaService,
        "limits",
        staticmethod(
            lambda: _limits(
                environments=["demo"],
                cost_reduction={"disable_voice_interview": True, "disable_file_upload": True},
                interview={"max_minutes": 3},
            )
        ),
    )

    response = await async_client.get("/config/runtime")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["features"]["voice_interview"] is False
    assert body["features"]["file_upload"] is False
    assert body["quota_enforced"] is True
    assert body["interview_max_minutes"] == 3
    # 配额数值要下发给前端：首页的"演示环境限制"直接用它，避免页面写死一份会过期的数字
    assert body["limits"]["tokens_per_ip"] == 1000
    assert body["limits"]["turns_per_day"] == 10


def test_voice_interview_defaults_to_enabled_outside_demo() -> None:
    """非演示环境不能误关语音——这是正常功能，不该被配额配置带走。"""
    assert UsageQuotaService.voice_interview_disabled() is False
    assert UsageQuotaService.file_upload_disabled() is False


@pytest.mark.anyio
async def test_upload_blocked_when_disabled(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """关掉附件上传后，上传接口必须直接拒绝（不能只靠前端藏按钮）。

    PDF / 图片解析出的全文会整段进上下文，一次上传能顶几十轮对话的 token，
    所以这条限制必须落在服务端。
    """
    import app.services.usage_quota_service as service_module

    headers = await register_and_login("uplock")
    monkeypatch.setattr(service_module, "settings", _FakeSettings())
    monkeypatch.setattr(
        UsageQuotaService,
        "limits",
        staticmethod(
            lambda: _limits(
                environments=["demo"],
                cost_reduction={"disable_file_upload": True},
            )
        ),
    )

    response = await async_client.post(
        "/upload/file",
        files={"file": ("note.txt", BytesIO(b"hello"), "text/plain")},
        headers=headers,
    )
    assert response.status_code == 403, response.text
    assert "附件上传" in response.json()["message"]


@pytest.mark.anyio
async def test_middleware_sets_client_ip_and_user(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 请求的 IP 与用户身份要能一路传到模型层（配额靠它定位）。"""
    headers = await register_and_login("quota")
    session_id = await create_session(async_client, headers)

    captured: dict[str, Any] = {}

    def factory(provider: str = "deepseek"):
        context = get_request_context()
        captured["client_ip"] = context.client_ip if context else None
        captured["user_id"] = context.user_id if context else None
        captured["scene"] = context.scene if context else None
        return GenericFakeChatModel(messages=iter([AIMessage(content="收到")]))

    monkeypatch.setattr(prompt_layer, "get_chat_model", factory)
    monkeypatch.setattr(
        "app.services.stream_chat_service.build_personalized_prompt", lambda **kwargs: None
    )
    monkeypatch.setattr(client_ip_module, "settings", _FakeTrustProxy(True))

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "配额测试"},
            headers={**headers, "X-Real-IP": TEST_IP_A},
        )
        assert response.status_code == 200, response.text
        assert captured["client_ip"] == TEST_IP_A
        assert captured["user_id"], "中间件应该从 Authorization 头里解出用户 ID"
        assert captured["scene"] == SCENE_CHAT, "对话链路要标记成 chat 场景"
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )
