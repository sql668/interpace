"""T10.5 回归测试：提示词版本管理接口（此前三个接口完全没有用例覆盖）。

覆盖 `GET /prompt/templates/{agent_name}/{scene}`、`POST /prompt/rollback`、
`GET /prompt/config/agents` 的正常路径与错误路径。

模板数据用一组专属探针 `(agent_name, scene)`，跑完即删，不碰开发库里的真实预置数据。
"""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import PromptTemplate
from app.services.prompt_template_service import AGENT_CONFIG

# 只在这个测试文件里存在的探针标识，避免与真实预置数据互相干扰。
PROBE_AGENT = "t105_probe_agent"
PROBE_SCENE = "t105_probe_scene"


@pytest.fixture
def probe_versions() -> Generator[tuple[int, int], None, None]:
    """造两条同 (agent, scene) 的模板版本：v1 未激活、v2 激活。

    返回 `(inactive_id, active_id)`；结束时把探针行删干净。
    """
    db: Session = SessionLocal()
    try:
        inactive = PromptTemplate(
            agent_name=PROBE_AGENT,
            scene=PROBE_SCENE,
            template_type=1,
            name="探针模板",
            description="旧版本",
            template_content="你是助手，当前版本 v1。",
            variables='["target_job"]',
            version=1,
            is_active=0,
        )
        active = PromptTemplate(
            agent_name=PROBE_AGENT,
            scene=PROBE_SCENE,
            template_type=1,
            name="探针模板",
            description="当前版本",
            template_content="你是助手，当前版本 v2。",
            variables='["target_job"]',
            version=2,
            is_active=1,
        )
        db.add_all([inactive, active])
        db.commit()
        yield inactive.id, active.id
    finally:
        db.query(PromptTemplate).filter(PromptTemplate.agent_name == PROBE_AGENT).delete()
        db.commit()
        db.close()


def _active_flags() -> dict[int, int]:
    """读出探针模板的 id -> is_active 映射，用于断言回滚结果。"""
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(PromptTemplate).filter(PromptTemplate.agent_name == PROBE_AGENT).all()
        )
        return {row.id: row.is_active for row in rows}
    finally:
        db.close()


@pytest.mark.anyio
async def test_agent_config_api(async_client: AsyncClient) -> None:
    """智能体配置列表：返回全部已登记智能体，且字段结构完整。"""
    response = await async_client.get("/prompt/config/agents")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    # 逐项断言，避免"返回了个空字典也算通过"。
    assert set(data.keys()) == set(AGENT_CONFIG.keys())
    for agent_name, config in data.items():
        assert config["scene"], f"{agent_name} 缺少 scene"
        assert config["name"], f"{agent_name} 缺少展示名"


@pytest.mark.anyio
async def test_template_versions_returns_all_versions(
    async_client: AsyncClient, probe_versions: tuple[int, int]
) -> None:
    """版本列表：同场景的全部版本都要返回，且按版本号倒序（最新在前）。"""
    inactive_id, active_id = probe_versions

    response = await async_client.get(f"/prompt/templates/{PROBE_AGENT}/{PROBE_SCENE}")
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data["agent_name"] == PROBE_AGENT
    assert data["scene"] == PROBE_SCENE

    versions = data["versions"]
    assert [item["version"] for item in versions] == [2, 1]
    assert [item["id"] for item in versions] == [active_id, inactive_id]
    # 激活标记要如实带回前端，否则前端无法标出"当前生效版本"。
    assert [item["is_active"] for item in versions] == [1, 0]


@pytest.mark.anyio
async def test_template_versions_not_found_returns_empty_data(
    async_client: AsyncClient,
) -> None:
    """未命中的场景不是异常：返回 200 + data=None。

    这里刻意固定住"查不到不算失败"这个约定——前端要靠 `data` 是否为空
    区分"没有历史版本"，若某天改成抛 404，前端会弹"资源不存在"，属于行为变更。
    """
    response = await async_client.get("/prompt/templates/no_such_agent/no_such_scene")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["code"] == 0
    assert body["data"] is None
    assert body["message"] == "未找到模板"


@pytest.mark.anyio
async def test_rollback_switches_active_version(
    async_client: AsyncClient, probe_versions: tuple[int, int]
) -> None:
    """回滚到旧版本：目标行变 is_active=1，同场景其他行变 0。"""
    inactive_id, active_id = probe_versions
    assert _active_flags() == {inactive_id: 0, active_id: 1}

    response = await async_client.post(
        "/prompt/rollback", json={"template_id": inactive_id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "回滚成功"

    # 唯一激活项必须只剩回滚目标——只置 1 不置 0 会出现两个生效版本。
    assert _active_flags() == {inactive_id: 1, active_id: 0}


@pytest.mark.anyio
async def test_rollback_missing_template_returns_404(async_client: AsyncClient) -> None:
    """回滚不存在的模板 ID：必须是 404，而不是被兜底捕获成 400。"""
    response = await async_client.post("/prompt/rollback", json={"template_id": 99999999})
    assert response.status_code == 404, response.text
    body = response.json()
    # 全局 HTTPException 处理器把 message 取自 detail，code 取自 status_code。
    assert body["code"] == 404
    assert body["message"] == "模板不存在"


@pytest.mark.anyio
async def test_rollback_invalid_payload_returns_422(async_client: AsyncClient) -> None:
    """请求体缺少 template_id：框架层参数校验直接返回 422，不进入业务逻辑。"""
    response = await async_client.post("/prompt/rollback", json={})
    assert response.status_code == 422, response.text
