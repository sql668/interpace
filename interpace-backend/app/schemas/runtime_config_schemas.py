"""运行时能力开关的响应模型（T12.4）。

前端需要知道"当前这套环境开放了哪些功能"才能决定界面上显示什么
（最典型的就是演示环境不显示「语音面试」按钮）。这些开关的**唯一事实来源**
是后端的 `config/demo_limits.json`，前端不再自己维护一份环境判断——
否则两边迟早会不一致，出现"按钮显示着但点了连不上"这种最难排查的状态。
"""

from pydantic import BaseModel, Field


class RuntimeFeatures(BaseModel):
    """当前环境开放的功能。"""

    voice_interview: bool = Field(description="是否开放语音面试（false 时前端不显示入口）")
    file_upload: bool = Field(description="是否开放附件上传（false 时前端不显示入口）")


class RuntimeNotice(BaseModel):
    """给用户看的提示文案。"""

    banner_text: str = Field(default="", description="环境横幅文案；空串表示不用展示横幅")


class RuntimeLimits(BaseModel):
    """当前生效的配额数值（只在演示环境有值）。

    首页要如实写明"演示环境能试到什么"，所以这些数字由后端下发，
    而不是前端自己抄一份——配置改了、页面还写着旧数字，那是骗人。
    """

    tokens_per_ip: int = Field(description="每个 IP 累计可消耗的 token 总量")
    turns_per_day: int = Field(description="每个 IP 每天最多几轮对话")
    quizzes_per_day: int = Field(description="每个 IP 每天最多提交几次答卷")
    evaluations_per_day: int = Field(description="每个 IP 每天最多生成几次面试复盘")
    voice_minutes_per_day: int = Field(description="每个 IP 每天最多几分钟语音面试")
    max_turns_per_session: int = Field(description="单个会话最多几轮")
    max_sessions: int = Field(description="单个账号最多几个会话")
    max_notes: int = Field(description="单个账号最多几条笔记")


class RuntimeConfigResponse(BaseModel):
    """运行时能力配置。"""

    app_env: str = Field(description="当前运行环境：development/demo/test/production")
    quota_enforced: bool = Field(description="当前环境是否受演示配额约束")
    features: RuntimeFeatures
    interview_max_minutes: int = Field(description="单场模拟面试时长上限（分钟）；0 表示不限")
    notice: RuntimeNotice
    limits: RuntimeLimits | None = Field(
        default=None, description="当前生效的配额数值；未启用配额时为 null"
    )
