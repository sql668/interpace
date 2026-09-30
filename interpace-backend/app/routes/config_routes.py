"""运行时能力开关路由（T12.4）。"""

from fastapi import APIRouter

from app.schemas.runtime_config_schemas import RuntimeConfigResponse
from app.services.usage_quota_service import UsageQuotaService

router = APIRouter()


@router.get(
    "/runtime",
    response_model=RuntimeConfigResponse,
    summary="获取当前环境的能力开关",
)
def get_runtime_config() -> RuntimeConfigResponse:
    """返回当前环境开放的功能与提示。

    **故意不鉴权**：登录页也可能需要它（比如显示"这是演示环境"），
    而且这里没有任何密钥或用户数据，只有环境名与布尔开关。
    """
    return RuntimeConfigResponse.model_validate(UsageQuotaService.runtime_snapshot())
