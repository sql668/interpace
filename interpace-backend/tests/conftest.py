"""pytest 共享夹具：各测试文件共用的进程内客户端与注册登录助手。"""

import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

# 业务接口统一挂在 /api/v1 前缀下（T10.1），探活 / 文档 / 根路径不带前缀。
#
# 这里把前缀放进 base_url 而不是给每个用例的路径加前缀：httpx 会把 base_url 的路径
# 与请求路径拼起来（注意 base_url 必须带结尾斜杠），所以用例里写的 `"/auth/login"`
# 实际请求的是 `/api/v1/auth/login`——测的仍是真实路径，只是省掉了 230 处重复。
# 需要访问**不带前缀**的接口时，用绝对地址（见 test_smoke.py 的探活用例）。
API_V1_BASE_URL = "http://test-server/api/v1/"

# 注册登录助手的签名：传入用户名前缀，返回可直接用于请求的鉴权头。
RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


@pytest.fixture(autouse=True)
def reset_rate_limit() -> None:
    """每个用例开始前清空内存限流窗口。

    注册接口限流是「每分钟 5 次」的固定窗口，而测试用的是同一个 ASGI 客户端，
    限流键完全相同——用例一多就会互相触发 429。清空窗口让每个用例从零计数，
    生产行为不受影响。
    """
    from app.core.rate_limit import reset_rate_limit_windows

    reset_rate_limit_windows()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    # 使用 ASGITransport 进行进程内请求，不依赖真实端口和外部网络。
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=API_V1_BASE_URL) as client:
        yield client


@pytest.fixture
def register_and_login(async_client: AsyncClient) -> RegisterAndLogin:
    """返回「注册新用户并登录、拿到鉴权头」的助手函数。

    /users、/notes 等接口都挂了 get_current_user，匿名访问会返回 401，
    所以调用前必须先拿到 access_token。
    """

    async def _register_and_login(prefix: str) -> dict[str, str]:
        # 随机后缀避免重复执行时触发用户名唯一约束；前缀截断保证总长不超过 20。
        username = f"{prefix[:10]}_{uuid4().hex[:8]}"
        password = "smoke123456"

        register_response = await async_client.post(
            "/auth/register",
            json={"username": username, "password": password},
        )
        assert register_response.status_code == 201

        login_response = await async_client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        assert login_response.status_code == 200

        return {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    return _register_and_login
