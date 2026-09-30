"""刷题评测相关的响应模型。

时间字段沿用项目约定：Unix 秒（与 `sessions` / `chat_messages` / `notes` 一致）。

**关键约束（T5.6 验收）**：返回给用户的题目里**不含 `reference_answer`**。
参考答案只在评分环节用（T5.7），答题阶段泄露就等于送答案。落库时留着它，
但接口层不暴露——所以这里单独定义 `QuizQuestionItem`，而不是直接序列化 ORM 行。
"""

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestionItem(BaseModel):
    """答题用的题目：**不含参考答案**。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int  # 题目序号，从 1 开始
    question: str  # 题干
    user_answer: str | None = None  # 用户作答（未提交时为 null）
    score: int | None = None  # 得分 0-100（未评分时为 null）
    analysis: str | None = None  # 逐题解析（未评分时为 null）


class QuizPaperItem(BaseModel):
    """卷子列表项：不含题目，供「按会话列出卷子」使用。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    message_id: int  # 入口消息 ID，前端据此把卡片挂到对应消息上
    target_job: str | None = None
    difficulty: str | None = None
    question_count: int
    status: int  # 0=待作答 1=已提交 2=已评分
    created_at: int


class QuizPaperDetail(QuizPaperItem):
    """卷子详情：带上题目列表。"""

    questions: list[QuizQuestionItem]


class QuizPaperListResponse(BaseModel):
    """按会话列出卷子的响应体。"""

    items: list[QuizPaperItem]
    total: int


class QuizAnswerItem(BaseModel):
    """一道题的用户作答。"""

    order_index: int = Field(gt=0, description="题目序号，与卷子里的 order_index 对应")
    answer: str = Field(default="", description="用户作答；留空表示放弃这道题")


class QuizSubmitRequest(BaseModel):
    """提交答案请求体。

    `answers` 传空数组等于「用库里已存的作答重新评分」——评分失败重试时用得上。
    """

    answers: list[QuizAnswerItem] = Field(default_factory=list)


class QuizSubmitResponse(BaseModel):
    """提交后的评分结果：总分 + 薄弱点 + 逐题得分与解析。"""

    paper_id: int
    status: int  # 提交成功后固定为 2（已评分）
    total_score: int | None = None  # 整卷得分；模型没给时为 null
    weak_topics: list[str] = Field(default_factory=list)
    questions: list[QuizQuestionItem] = Field(default_factory=list)
