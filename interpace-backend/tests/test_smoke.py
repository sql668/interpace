from io import BytesIO
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from uuid import uuid4

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

@pytest.mark.anyio
async def test_health_ready(async_client: AsyncClient) -> None:
    """验证服务就绪检查（服务 + 数据库）。"""
    # 探活接口刻意不带 /api/v1 前缀（T10.1），所以要写绝对地址绕开 base_url。
    response = await async_client.get("http://test-server/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_docs_accessible(async_client: AsyncClient) -> None:
    """验证接口文档可访问。"""
    response = await async_client.get("http://test-server/docs")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_business_path_requires_api_v1_prefix(async_client: AsyncClient) -> None:
    """T10.1：业务接口必须带 /api/v1，裸路径应当 404。

    这条用例是"前缀真的加上了"的直接证据——如果哪天有人把前缀摘掉，
    conftest 的 base_url 会让全部用例一起红，但红的原因需要这条来定位。
    """
    without_prefix = await async_client.get("http://test-server/users")
    assert without_prefix.status_code == 404

    with_prefix = await async_client.get("http://test-server/api/v1/users")
    # 未带鉴权头，所以是 401 而不是 404：路由存在，只是没登录。
    assert with_prefix.status_code == 401


@pytest.mark.anyio
async def test_users_list_api(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """用户列表接口需要鉴权：匿名 401，携带令牌 200。"""
    anonymous_response = await async_client.get("/users")
    assert anonymous_response.status_code == 401

    headers = await register_and_login("list")
    response = await async_client.get("/users", headers=headers)
    assert response.status_code == 200


@pytest.mark.anyio
async def test_user_crud_apis(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """验证用户核心接口链路（创建/详情/更新）。"""
    headers = await register_and_login("crud")

    # 追加随机后缀，避免重复执行测试时触发用户名唯一约束冲突。
    suffix = uuid4().hex[:8]
    username = f"smoke_{suffix}"
    updated_username = f"smoke_u_{suffix}"

    create_response = await async_client.post(
        "/users",
        json={"username": username, "password": "smoke123456"},
        headers=headers,
    )
    assert create_response.status_code == 201
    created_user = create_response.json()["user"]
    user_id = created_user["id"]

    get_response = await async_client.get(f"/users/{user_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["username"] == username

    update_response = await async_client.put(
        f"/users/{user_id}",
        json={"username": updated_username, "password": "smoke654321"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["username"] == updated_username

    # delete_response = await async_client.delete(f"/users/{user_id}")
    # assert delete_response.status_code == 200


@pytest.mark.anyio
async def test_upload_file_api(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """验证文件上传接口可用（同样需要鉴权）。"""
    headers = await register_and_login("upload")

    files = {"file": ("sample.txt", BytesIO(b"hello upload"), "text/plain")}
    data = {"storage_scene": "1"}
    upload_response = await async_client.post(
        "/upload/file",
        data=data,
        files=files,
        headers=headers,
    )
    assert upload_response.status_code == 201
    body = upload_response.json()
    assert body["resource_type"] == 0
    assert body["storage_scene"] == 1


@pytest.mark.anyio
async def test_avatar_upload_writes_user_avatar(async_client: AsyncClient) -> None:
    """T0.4：以「头像用途」上传图片后，users.avatar 应被回写。"""
    suffix = uuid4().hex[:8]
    username = f"avatar_{suffix}"
    password = "smoke123456"

    register_response = await async_client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["user"]["id"]

    login_response = await async_client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    # 只有「图片 + upload_purpose=1」才会回写 users.avatar
    files = {"file": ("avatar.png", BytesIO(b"fake-png-bytes"), "image/png")}
    upload_response = await async_client.post(
        "/upload/file",
        data={"upload_purpose": "1", "storage_scene": "3"},
        files=files,
        headers=headers,
    )
    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["resource_type"] == 1
    assert uploaded["storage_scene"] == 3
    assert uploaded["file_path"].startswith("minio://")
    assert uploaded["expire_time"] is None  # 永久存储没有过期时间

    profile_response = await async_client.get(f"/users/{user_id}", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["avatar"] == uploaded["file_path"]

    # 头像路径能取回真实字节——前端就是靠这条路径把头像渲染出来的
    avatar_response = await async_client.get(
        "/resources/content",
        params={"storage_path": profile_response.json()["avatar"]},
        headers=headers,
    )
    assert avatar_response.status_code == 200
    assert avatar_response.content == b"fake-png-bytes"
    assert avatar_response.headers["content-type"].startswith("image/png")


@pytest.mark.anyio
async def test_resource_content_requires_ownership(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """T3.4：资源内容接口只能读自己的资源，字节要与上传一致。"""
    owner = await register_and_login("resowner")
    other = await register_and_login("resother")

    payload = b"hello resource content"
    upload = await async_client.post(
        "/upload/file",
        files={"file": ("sample.txt", BytesIO(payload), "text/plain")},
        headers=owner,
    )
    assert upload.status_code == 201
    resource_id = upload.json()["resource_id"]
    file_path = upload.json()["file_path"]

    content = await async_client.get(f"/resources/{resource_id}/content", headers=owner)
    assert content.status_code == 200
    assert content.content == payload
    assert content.headers["content-type"].startswith("text/plain")

    # 别人的资源、不存在的资源，一律 404；未登录 401
    assert (
        await async_client.get(f"/resources/{resource_id}/content", headers=other)
    ).status_code == 404
    assert (
        await async_client.get("/resources/999999999/content", headers=owner)
    ).status_code == 404
    assert (await async_client.get(f"/resources/{resource_id}/content")).status_code == 401

    # 按存储路径读取（头像走的就是这条路）同样只能读自己的
    assert (
        await async_client.get(
            "/resources/content", params={"storage_path": file_path}, headers=other
        )
    ).status_code == 404
    assert (
        await async_client.get(
            "/resources/content", params={"storage_path": file_path}, headers=owner
        )
    ).status_code == 200
