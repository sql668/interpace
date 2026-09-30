"""T10.5 回归测试：`/auth` 的错误路径，以及此前零覆盖的 `/auth/refresh`。

注册/登录的成功链路已经在 conftest 的 `register_and_login` 里天天跑，这里只盯
「有问题时会不会安静地放过」：刷新令牌无效、拿访问令牌当刷新令牌用、必填字段缺失、
密码错误、用户不存在。
"""

import base64
import json
from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient

from api_helpers import purge_user

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _current_user_id(headers: dict[str, str]) -> int:
    """从鉴权头里的 JWT 解出用户 ID（只解码不验签，测试够用）。"""
    token = headers["Authorization"].split(" ", 1)[1]
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    return int(json.loads(base64.urlsafe_b64decode(payload + padding))["sub"])


@pytest.mark.anyio
async def test_refresh_issues_usable_access_token(async_client: AsyncClient) -> None:
    """正常路径：用刷新令牌换到的新访问令牌必须真的能过鉴权。"""
    username = f"arefresh_{uuid4().hex[:8]}"
    password = "smoke123456"
    register = await async_client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert register.status_code == 201, register.text
    user_id = int(register.json()["user"]["id"])

    try:
        login = await async_client.post(
            "/auth/login", json={"username": username, "password": password}
        )
        assert login.status_code == 200, login.text
        refresh_token = login.json()["refresh_token"]

        refreshed = await async_client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refreshed.status_code == 200, refreshed.text
        body = refreshed.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        # 只断言"返回了字符串"太弱：拿新令牌真实访问一次受保护接口才算数。
        new_headers = {"Authorization": f"Bearer {body['access_token']}"}
        assert _current_user_id(new_headers) == user_id
        probe = await async_client.get("/users", headers=new_headers)
        assert probe.status_code == 200, probe.text
    finally:
        purge_user(user_id)


@pytest.mark.anyio
async def test_refresh_rejects_invalid_token(async_client: AsyncClient) -> None:
    """刷新令牌是乱码：401，而不是 500 或放行。"""
    response = await async_client.post(
        "/auth/refresh", json={"refresh_token": "not-a-jwt"}
    )
    assert response.status_code == 401, response.text
    assert response.json()["message"] == "刷新令牌无效或已过期"


@pytest.mark.anyio
async def test_refresh_rejects_access_token(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """拿访问令牌当刷新令牌用：必须按 `typ` 拒绝（401）。

    两种令牌用的是同一个密钥，只验签名不验类型就会把有效期短的访问令牌
    当成长期刷新令牌，等于把令牌有效期绕过去了。
    """
    headers = await register_and_login("atyp")
    access_token = headers["Authorization"].split(" ", 1)[1]

    response = await async_client.post(
        "/auth/refresh", json={"refresh_token": access_token}
    )
    assert response.status_code == 401, response.text
    assert response.json()["message"] == "刷新令牌无效或已过期"


@pytest.mark.anyio
async def test_refresh_missing_field_returns_422(async_client: AsyncClient) -> None:
    """缺少 refresh_token：框架层 422，不进业务逻辑。"""
    response = await async_client.post("/auth/refresh", json={})
    assert response.status_code == 422, response.text
    assert response.json()["message"] == "请求参数校验失败"


@pytest.mark.anyio
async def test_login_error_paths(async_client: AsyncClient) -> None:
    """登录：密码错误与用户不存在都返回同一句话（不区分，避免账号枚举）。"""
    username = f"alogin_{uuid4().hex[:8]}"
    password = "smoke123456"
    register = await async_client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert register.status_code == 201, register.text
    user_id = int(register.json()["user"]["id"])

    try:
        wrong_password = await async_client.post(
            "/auth/login", json={"username": username, "password": "smoke654321"}
        )
        assert wrong_password.status_code == 401, wrong_password.text
        assert wrong_password.json()["message"] == "用户名或密码错误"

        unknown_user = await async_client.post(
            "/auth/login",
            json={"username": f"alogin_no_{uuid4().hex[:8]}", "password": password},
        )
        assert unknown_user.status_code == 401, unknown_user.text
        assert unknown_user.json()["message"] == "用户名或密码错误"

        too_short = await async_client.post(
            "/auth/login", json={"username": "ab", "password": "123"}
        )
        assert too_short.status_code == 422, too_short.text
    finally:
        purge_user(user_id)
