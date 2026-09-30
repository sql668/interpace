"""面试复盘相关的响应模型（对应 T8.2）。

时间字段沿用项目约定：Unix 秒。
"""

from pydantic import BaseModel, ConfigDict, Field


class InterviewEvaluationResult(BaseModel):
    """一场面试的复盘结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    interview_id: int
    summary: str  # 整体表现总结
    weak_topics: list[str] = Field(default_factory=list)  # 薄弱知识点
    suggestions: list[str] = Field(default_factory=list)  # 改进建议
    # 复盘来源：0=面试记录里的问答文本，1=上传的录音转写（T8.3）
    source: int = 0
    # 来源为录音时对应的资源 ID（可据此回放）；问答文本复盘时为 None
    resource_id: int | None = None
    # 输入规模：问答文本复盘记问答条数，录音复盘记转写分句数。
    # 小于当前实际条数说明之后又答了几轮（或换了录音），可以提示重新生成
    qa_count: int
    created_at: int
    updated_at: int


class InterviewEvaluationResponse(BaseModel):
    """生成复盘的响应体：一定带结果。"""

    message: str  # 人类可读提示
    evaluation: InterviewEvaluationResult


class InterviewEvaluationQueryResponse(BaseModel):
    """读取复盘的响应体：**没生成过时 `evaluation` 为 null，而不是 404**。

    为什么不返回 404：「这场面试还没复盘」是**正常状态**（用户还没点生成），
    不是错误。用 404 表达会让前端每次打开面板都产生一次错误响应——
    更糟的是项目里的全局拦截器对 404 统一弹「资源不存在」，
    用户会莫名其妙看到一个红色报错（真机反馈就是这么发现的）。
    真正该 404 的只有「面试记录不存在 / 不是你的」。
    """

    message: str
    evaluation: InterviewEvaluationResult | None = None


class InterviewEvaluationFromAudioRequest(BaseModel):
    """用上传录音生成复盘的请求体（T8.3）。"""

    resource_id: int = Field(gt=0, description="已上传的面试录音资源ID")


class InterviewEvaluationFromAudioResponse(InterviewEvaluationResponse):
    """录音复盘的响应体：额外把转写文本带回去。

    为什么要回传转写：识别错的地方用户一眼就能看出来，
    否则「AI 的结论为什么是这样」无从判断。
    """

    transcript: str


class InterviewFinishResponse(BaseModel):
    """结束面试的响应体（T7.8）。

    `already_finished=True` 表示这场面试之前就结束了（重复点击）。
    结束本身**不触发复盘**：复盘由前端紧接着调用复盘接口生成，
    这样「结束」是瞬时的，而「生成复盘」可以有独立的等待状态与失败重试。
    """

    message: str
    interview_id: int
    status: int  # 1=已结束
    interview_duration: int  # 面试时长（秒）
    qa_count: int  # 这场面试的问答条数
    already_finished: bool
