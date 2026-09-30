"""T10.5 回归测试：`/users` 接口的错误路径（原有用例只覆盖了正常链路）。

补齐 AGENTS.md 要求的「每个路由至少一个正常路径 + 一个错误路径」：
未登录 401、路径参数校验 422、资源不存在 404、唯一性冲突 409、空更新 400。
成功建的临时用户用完即删，不给开发库留残留。
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient

from api_helpers import purge_user

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


async def _create_user(
    async_client: AsyncClient, headers: dict[str, str], username: str
) -> int:
    """建一个用户，返回其 ID（断言创建成功）。"""
    response = await async_client.post(
        "/users",
        json={"username": username, "password": "smoke123456"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["user"]["id"])


@pytest.mark.anyio
async def test_users_endpoints_require_auth(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """匿名访问五个用户接口，必须一律 401（原先只验了列表接口）。"""
    headers = await register_and_login("uauth")
    user_id = await _create_user(async_client, headers, f"uauth_{uuid4().hex[:8]}")

    try:
        anonymous_calls = [
            ("post", "/users", {"json": {"username": "x", "password": "y"}}),
            ("get", "/users", {}),
            ("get", f"/users/{user_id}", {}),
            ("put", f"/users/{user_id}", {"json": {"username": "y"}}),
            ("delete", f"/users/{user_id}", {}),
        ]
        for method, path, kwargs in anonymous_calls:
            response = await getattr(async_client, method)(path, **kwargs)
            assert response.status_code == 401, f"{method.upper()} {path} 未拦截匿名访问"
    finally:
        purge_user(user_id)


@pytest.mark.anyio
async def test_get_user_not_found_and_invalid_id(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """详情接口：不存在的 ID 返回 404，非法 ID（<=0）在框架层被拦成 422。"""
    headers = await register_and_login("uget")

    missing = await async_client.get("/users/99999999", headers=headers)
    assert missing.status_code == 404, missing.text
    assert missing.json()["message"] == "用户不存在"

    # Path(gt=0) 的作用：非法值不该进业务层，也就不会退化成 404 还是 500 的争论。
    invalid = await async_client.get("/users/0", headers=headers)
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["message"] == "请求参数校验失败"


@pytest.mark.anyio
async def test_update_user_error_paths(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """更新接口：空请求体 400，目标不存在 404，用户名撞车 409。"""
    headers = await register_and_login("uupd")
    other_username = f"uupd_other_{uuid4().hex[:8]}"
    user_id = await _create_user(async_client, headers, f"uupd_{uuid4().hex[:8]}")
    other_id = await _create_user(async_client, headers, other_username)

    try:
        # 两个字段都不传：业务层显式拒绝，避免"成功但什么都没改"的假成功。
        empty = await async_client.put(f"/users/{user_id}", json={}, headers=headers)
        assert empty.status_code == 400, empty.text
        assert empty.json()["message"] == "请至少提供一个需要更新的字段"

        missing = await async_client.put(
            "/users/99999999", json={"username": "nobody"}, headers=headers
        )
        assert missing.status_code == 404, missing.text

        # 改成另一个已存在的用户名：唯一性校验要排除自己、命中别人。
        conflict = await async_client.put(
            f"/users/{user_id}", json={"username": other_username}, headers=headers
        )
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["message"] == "用户名已被占用"
    finally:
        purge_user(user_id)
        purge_user(other_id)


@pytest.mark.anyio
async def test_create_user_error_paths(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """创建接口：重复用户名 409，弱密码 400，字段缺失 422。"""
    headers = await register_and_login("ucreate")
    username = f"ucreate_{uuid4().hex[:8]}"
    user_id = await _create_user(async_client, headers, username)

    try:
        duplicated = await async_client.post(
            "/users",
            json={"username": username, "password": "smoke123456"},
            headers=headers,
        )
        assert duplicated.status_code == 409, duplicated.text
        assert duplicated.json()["message"] == "用户名已被占用"

        # 密码长度先被 Pydantic 卡在 8 位，所以这里用刚好 8 位、但只有数字的
        # "24681357" 才能走到业务层的强度校验，验证它返回的是 400 而不是 422。
        # （不能用 "12345678"：它会先命中"密码过于常见"那条规则，断言不到字母数字规则。）
        weak = await async_client.post(
            "/users",
            json={"username": f"ucreate_w_{uuid4().hex[:8]}", "password": "24681357"},
            headers=headers,
        )
        assert weak.status_code == 400, weak.text
        assert weak.json()["message"] == "密码必须同时包含字母和数字"

        missing_field = await async_client.post(
            "/users", json={"username": f"ucreate_m_{uuid4().hex[:8]}"}, headers=headers
        )
        assert missing_field.status_code == 422, missing_field.text
    finally:
        purge_user(user_id)


@pytest.mark.anyio
async def test_delete_user_not_found_and_invalid_id(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """删除接口：不存在的 ID 404，非法 ID 422。"""
    headers = await register_and_login("udel")

    missing = await async_client.delete("/users/99999999", headers=headers)
    assert missing.status_code == 404, missing.text
    assert missing.json()["message"] == "用户不存在"

    invalid = await async_client.delete("/users/0", headers=headers)
    assert invalid.status_code == 422, invalid.text
