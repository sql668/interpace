"""用户画像的请求/响应模型（T9.3）。

两段结构对应两类字段，来源与可信度完全不同（见阶段 9 的「画像来源策略」）：

- `intent`：意图类（目标岗位 / 目标级别 / 经验年限）——用户想要什么；
- `memories`：能力类明细（技能 / 薄弱点 / 答题方法）——用户会什么，逐条带掌握程度与来源。

时间字段沿用项目约定：Unix 秒。
"""

from pydantic import BaseModel, ConfigDict, Field


class ProfileIntent(BaseModel):
    """意图类字段。"""

    model_config = ConfigDict(from_attributes=True)

    target_job: str | None = None
    years_experience: str | None = None
    target_level: str | None = None


class ProfileMemoryItem(BaseModel):
    """一条能力记忆。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: int  # 0=技能 1=薄弱点 2=答题方法
    category_label: str = ""  # 展示用中文名
    name: str
    mastery: int  # 0-100
    mastery_label: str = ""  # 对外只给四档：熟练/熟悉/了解/待加强
    source: int  # 0=模型推断 1=用户自述 2=简历声明 3=行为证据
    source_label: str = ""  # 展示用中文名
    confidence: int
    evidence_count: int
    last_evidence_at: int | None = None
    pending_approval: int = 0  # 1=自动抽取待用户确认（T9.9）
    updated_at: int


class UserProfileResponse(BaseModel):
    """当前用户的完整画像。"""

    intent: ProfileIntent
    memories: list[ProfileMemoryItem] = Field(default_factory=list)
    # 兼容字段：既有提示词注入读的就是这两个扁平列表（JSON 列是派生缓存）
    target_skills: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)


class ProfileIntentUpdateRequest(BaseModel):
    """更新意图类字段；只更新显式传入的项。"""

    target_job: str | None = Field(default=None, max_length=128)
    years_experience: str | None = Field(default=None, max_length=64)
    target_level: str | None = Field(default=None, max_length=32)


class ProfileMemoryCreateRequest(BaseModel):
    """手动新增一条能力记忆（用户自建，直接生效）。"""

    category: int = Field(ge=0, le=2, description="0技能 1薄弱点 2答题方法")
    name: str = Field(min_length=1, max_length=128)
    mastery: int = Field(default=50, ge=0, le=100, description="掌握程度 0-100")


class ProfileMemoryUpdateRequest(BaseModel):
    """修改一条能力记忆；只更新显式传入的项。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    mastery: int | None = Field(default=None, ge=0, le=100)


class ProfileMemoryLogItem(BaseModel):
    """一条记忆变更日志（T9.9）：用于回答「系统原来记的是什么」。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    memory_id: int | None = None
    category: int
    category_label: str = ""
    name: str
    action: str  # created/merged/approved/rejected/updated/deleted
    action_label: str = ""
    before_json: str | None = None
    after_json: str | None = None
    created_at: int
