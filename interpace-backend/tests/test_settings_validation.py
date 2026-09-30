"""T10.6 回归测试：配置校验必须发生在**启动时**，而不是运行期只打个警告。

背景：`.env` 里的 `JWT_SECRET` 曾经只有 20 字节，PyJWT 只打一条
`InsecureKeyLengthWarning` 就继续跑了——没人注意到，一直留到 T0.1 跑测试时才暴露。
所以密钥长度改成启动即校验。
"""

import sys
import os
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import MIN_JWT_SECRET_BYTES, Settings


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """只跳过分层 `.env` 文件，仍然读 `os.environ`——否则测试设的变量会被一起屏蔽。

    （第一版就是整个 stub 掉了加载器，结果 `monkeypatch.setenv` 设的值看不见，
    断言报的是「MYSQL_URL 必填」，白白查了一轮。）
    """
    from app.core import settings as settings_module

    monkeypatch.setattr(
        settings_module, "_load_layered_env", lambda: ("test", dict(os.environ))
    )


def test_short_jwt_secret_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """密钥过短时启动直接失败，并给出可执行的生成命令。"""
    _clear_env(monkeypatch)
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    monkeypatch.setenv("JWT_SECRET", "too-short-secret")  # 16 字节

    with pytest.raises(RuntimeError) as exc:
        Settings.from_env()
    message = str(exc.value)
    assert "JWT_SECRET" in message
    assert str(MIN_JWT_SECRET_BYTES) in message
    assert "token_urlsafe" in message  # 报错里要给出怎么生成


def test_long_enough_jwt_secret_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """长度达标就通过（32 字节是下限，不是「必须更长」）。"""
    _clear_env(monkeypatch)
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    monkeypatch.setenv("JWT_SECRET", "x" * MIN_JWT_SECRET_BYTES)

    settings = Settings.from_env()
    assert len(settings.jwt_secret.encode("utf-8")) == MIN_JWT_SECRET_BYTES


def test_missing_jwt_secret_still_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """完全没配时报的仍是「必填」，不要被长度校验抢了信息。"""
    _clear_env(monkeypatch)
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError) as exc:
        Settings.from_env()
    assert "required" in str(exc.value)


def test_cors_origins_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS 白名单要能按环境配（T11.6）。

    原来是写死在 main.py 里的三个本机地址：生产同源部署用不到它，
    但一旦前后端分域，就得能改，而不是去改代码。
    """
    _clear_env(monkeypatch)
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    monkeypatch.setenv("JWT_SECRET", "x" * MIN_JWT_SECRET_BYTES)
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://interpace.example.com, https://www.interpace.example.com ,"
    )

    settings = Settings.from_env()
    # 逗号分隔、自动去空格、空项丢弃
    assert settings.cors_origins == (
        "https://interpace.example.com",
        "https://www.interpace.example.com",
    )


def test_cors_origins_default_to_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """不配就退回本机开发地址，且**不会**变成"允许所有来源"。"""
    _clear_env(monkeypatch)
    monkeypatch.setenv("MYSQL_URL", "mysql+pymysql://u:p@127.0.0.1:3306/db")
    monkeypatch.setenv("JWT_SECRET", "x" * MIN_JWT_SECRET_BYTES)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings.from_env()
    assert settings.cors_origins  # 非空
    assert all("localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origins)
    assert "*" not in settings.cors_origins
