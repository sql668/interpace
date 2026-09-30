"""项目 ORM 模型定义。"""

import time
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    TEXT,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _unix_ts() -> int:
    """返回当前 Unix 秒时间戳。"""
    return int(time.time())


class User(Base):
    """用户表：系统登录主体。"""

    __tablename__ = "users"

    # 自增主键，内部唯一标识。
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # unique=True 数据库层防重名；index=True 便于注册时唯一性查询。
    username: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False)
    # 仅存密码哈希，不存明文。
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 插入时未赋值则由 ORM 用 default 写入当前 Unix 秒。
    create_time: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        comment="创建时间 Unix 秒",
    )


class UserProfile(Base):
    """用户个人信息表：存储已提取的用户信息（来源：简历解析或表单填写）"""

    __tablename__ = "user_profiles"
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        {"comment": "用户个人信息表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), 
        nullable=False, unique=True, 
        comment="用户FK（一对一关系）")
    
    target_job: Mapped[str | None] = mapped_column(
        String(128), nullable=True, 
        comment="目标岗位，如'Python后端工程师'")
    
    years_experience: Mapped[str | None] = mapped_column(
        String(64), nullable=True, 
        comment="工作经验，如'3年'")
    
    target_level: Mapped[str | None] = mapped_column(
        String(32), nullable=True, 
        comment="目标等级：初级/中级/高级")
    
    target_skills: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, 
        comment="已掌握技能 JSON数组")
    
    weak_topics: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, 
        comment="薄弱点 JSON数组")
    
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, 
        default=_unix_ts,
        comment="创建时间 Unix秒")
    
    updated_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, 
        default=_unix_ts, onupdate=_unix_ts,
        comment="更新时间 Unix秒")


class Session(Base):
    """会话表：承载用户的学习/面试/笔记会话。"""

    __tablename__ = "sessions"
    __table_args__ = {"comment": "会话表"}

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=False, comment="用户 FK"
    )
    session_model: Mapped[int] = mapped_column(
        nullable=False, comment="会话模式：0=学习，1=面试，2=笔记")
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="标题")
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        comment="创建时间 Unix 秒",
    )


class ChatMessage(Base):
    """消息表：记录用户请求与模型响应。"""

    __tablename__ = "chat_messages"
    __table_args__ = (
        # 按会话拉取消息并按时间排序时走索引，避免全表扫。
        Index("idx_session_id_created_at", "session_id", "created_at"),
        {"comment": "消息表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id"), nullable=False, comment="用户 FK")
    session_id: Mapped[int] = mapped_column(ForeignKey(
        "sessions.id"), nullable=False, comment="会话 FK")
    select_model: Mapped[int] = mapped_column(
        nullable=False,
        comment="选择模式：0=默认，1=知识精讲，2=刷题，3=简历优化，4=模拟面试，5=面试复盘",
    )
    request_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, comment="请求唯一标识"
    )
    # MEDIUMTEXT：单条请求/回复可能很长。
    request_text: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="用户请求文本")
    response_text: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="模型响应文本")
    # 仅存附件段信息（file/image/audio），不存聊天正文文本。
    request_segments: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True, comment="用户请求附件段 JSON")
    # 仅存附件段信息（file/image/audio），不存聊天正文文本。
    response_segments: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True, comment="模型响应附件段 JSON")
    # 消息状态：0=常规聊天；1=面试转写入口（尚无写入点）；2=用户主动停止；
    # 3=题库入口；4=画像待确认。
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        comment="消息状态：0常规聊天，1面试转写入口，2用户主动停止，3题库入口，4画像待确认",
    )
    # 关联面试记录ID，status=1 时可用。
    interview_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
        comment="面试记录ID（status=1 时可用）",
    )
    file_extracted_text: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=True, comment="从文件中总结的文本(对话上下文用)")
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        comment="创建时间 Unix 秒",
    )


class Resource(Base):
    """资源治理总表：统一管理文件、图片、音频元数据。"""

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("file_hash", "user_id", name="uk_file_hash_user_id"),
        {"comment": "资源治理总表（单表方案）"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="资源主键ID",
    )
    resource_type: Mapped[int] = mapped_column(
        nullable=False, comment="资源类型：0=文件，1=图片，2=音频"
    )
    storage_scene: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        comment="存储场景：0=长过期，1=短过期，2=只提取内容不存原文件，3=永久存储",
    )
    upload_purpose: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        comment="上传用途：0=普通资源，1=用户头像",
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名")
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="文件MD5")
    storage_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="存储路径")
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id"), nullable=False, comment="上传用户ID")
    expire_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="过期时间")
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )


class Interview(Base):
    """面试记录表：沉淀一场模拟面试的一问一答过程。"""

    __tablename__ = "interviews"
    __table_args__ = (
        Index("idx_session_id_message_id", "session_id", "message_id"),
        {"comment": "面试记录：一问一答 JSON（qa_object），入口见 message_id"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="用户 FK（用于快速按用户过滤面试记录）",
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
        comment="会话 FK",
    )
    # 唯一：一条入口 chat 消息对应一场面试记录。
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id"),
        unique=True,
        nullable=False,
        comment="面试入口消息 FK",
    )
    # 示例：[{"id":"uuid","question":"...","answer":"...","created_at":1717171717}]，created_at 为 Unix 秒。
    qa_object: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        comment="一问一答 JSON",
    )
    interview_duration: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        comment="面试时长秒",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
        server_default="0",
        comment="状态：0进行中 1已结束 2异常",
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        comment="面试开始 Unix 秒",
    )
    # BIGINT 无库端 ON UPDATE；ORM 更新行时由 onupdate 写入当前秒。原生 SQL 更新需自行设该列。
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="最后更新 Unix 秒",
    )


class PromptTemplate(Base):
    """提示词模板版本管理表：统一管理各智能体的提示词模板，支持版本控制和复用。"""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("idx_agent_scene", "agent_name", "scene"),
        {"comment": "提示词模板版本管理表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="模板ID")
    agent_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="智能体名称，公共模板此字段为空")
    scene: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="业务场景")
    template_type: Mapped[int] = mapped_column(
        default=1,
        server_default="1",
        comment="模板类型：1-私有 2-公共",
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="模板名称")
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="版本变更说明")
    template_content: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="提示词正文（含变量占位）")
    variables: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment='模板变量JSON列表，如["target_job","weak_points"]',
    )
    version: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1", comment="版本号，整数自增")
    is_active: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        comment="是否生效：1-是 0-否",
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        comment="创建时间 Unix 秒",
    )


class Note(Base):
    """笔记表：用户手写、或从对话 / 复盘一键存入的学习笔记。

    设计说明（对应 T2.1 的结论）：笔记自己就是列表单位，**不关联 `sessions`**。
    早先设想的「`session_model=2` 会话当笔记本分组」已经放弃——笔记本会话永远
    不会产生聊天消息，用它做分组只会带来语义上的别扭。
    """

    __tablename__ = "notes"
    __table_args__ = (
        # 列表按「最近更新」倒序分页，走这个联合索引。
        Index("idx_notes_user_updated", "user_id", "updated_at"),
        {"comment": "笔记表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户 FK")
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="笔记标题")
    content: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="笔记正文（富文本 HTML）")
    source_type: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        comment="来源：0=手写，1=来自对话，2=来自复盘",
    )
    # 软引用：故意不加外键。笔记正文是复制过来的，源消息被删（例如整个会话被删）
    # 不应该连带影响用户自己的笔记，所以这里只留一个可能失效的出处 ID。
    source_message_id: Mapped[int | None] = mapped_column(
        nullable=True, comment="来源消息 ID（source_type=1 时可用，软引用无外键）")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="最后更新 Unix 秒",
    )


class QuizPaper(Base):
    """题库表：一次出题（一份卷子）。

    设计说明（对应 T5.2）：拆成 papers + questions 两张表，「一次出题」与
    「一道题」的字段不混在一起，后续按岗位 / 难度做统计才好做。

    一份卷子只支持一次作答——用户的答案、得分、解析直接挂在题目行上。
    以后要做「重做一遍再对比」得再加 submissions 表，v1 不提前加。
    """

    __tablename__ = "quiz_papers"
    __table_args__ = (
        # 前端按「会话 + 入口消息」找卷子，走这个联合索引。
        Index("idx_quiz_papers_session_message", "session_id", "message_id"),
        {"comment": "题库表：一次出题"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True, comment="用户 FK")
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, comment="会话 FK")
    # 唯一：一条入口消息对应一份卷子。
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id"),
        unique=True,
        nullable=False,
        comment="题库入口消息 FK",
    )
    target_job: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="目标岗位，如'Python 后端'")
    difficulty: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="难度：初级 / 中级 / 高级")
    question_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="题目数量")
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        index=True,
        comment="状态：0待作答 1已提交 2已评分",
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="最后更新 Unix 秒",
    )


class QuizQuestion(Base):
    """题库题目表：一道题，含参考答案与（作答后的）用户答案、得分、解析。"""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        Index("idx_quiz_questions_paper", "paper_id", "order_index"),
        {"comment": "题库题目表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_papers.id"), nullable=False, comment="所属卷子 FK")
    order_index: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="题目序号，从 1 开始")
    question: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="题干")
    # 参考答案允许为空：模型偶尔漏给时不该整批写入失败，缺了在评测里单独提示。
    reference_answer: Mapped[str | None] = mapped_column(
        MEDIUMTEXT, nullable=True, comment="参考答案")
    user_answer: Mapped[str | None] = mapped_column(
        MEDIUMTEXT, nullable=True, comment="用户作答（未提交时为空）")
    score: Mapped[int | None] = mapped_column(
        nullable=True, comment="得分 0-100（未评分时为空）")
    analysis: Mapped[str | None] = mapped_column(
        MEDIUMTEXT, nullable=True, comment="逐题解析（未评分时为空）")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")


class ProfileProposal(Base):
    """画像待确认表：简历里抽取出的画像信息，等用户确认后才写进 `user_profiles`。

    为什么单独存一张表（对应 T6.2 / 决策 D11）：
    - 简历解析可能出错，**直接写画像会污染之后所有对话**（提示词每轮都注入画像），
      所以先落成「待确认」，用户确认（可改）后才写入；
    - 待确认状态要能跨刷新保留，所以必须落库，不能只放在前端内存里；
    - 一条入口消息对应一条待确认记录（`message_id` 唯一）。
    """

    __tablename__ = "profile_proposals"
    __table_args__ = (
        Index("idx_profile_proposals_session_message", "session_id", "message_id"),
        {"comment": "画像待确认表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True, comment="用户 FK")
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, comment="会话 FK")
    # 唯一：一条入口消息对应一份待确认记录。
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id"),
        unique=True,
        nullable=False,
        comment="来源消息 FK",
    )
    # 抽取出的画像字段原样存 JSON，字段与 user_profiles 对齐。
    payload: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="抽取出的画像字段 JSON")
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        index=True,
        comment="状态：0待确认 1已确认 2已忽略",
    )
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="更新时间 Unix 秒",
    )


class UserMemoryLog(Base):
    """能力记忆的变更日志（T9.9）：记录被覆盖或删除前的原文，便于回溯。

    `memory_id` 故意**不加外键**：被删除的记忆恰恰是最需要留痕的，
    加了外键反而会因为「记忆没了」而删不掉或留着空引用。
    条目名与类别在这里冗余存一份，保证记忆被删之后日志仍然可读。
    """

    __tablename__ = "user_memory_logs"
    __table_args__ = (
        Index("idx_user_memory_logs_user", "user_id"),
        {"comment": "能力记忆变更日志"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户 FK（隔离键）")
    memory_id: Mapped[int | None] = mapped_column(
        nullable=True, comment="对应的记忆条目 ID（无外键，条目删除后仍保留日志）")
    category: Mapped[int] = mapped_column(
        nullable=False, comment="类别快照：0技能 1薄弱点 2答题方法")
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="条目名快照")
    # created / merged / approved / rejected / updated / deleted
    action: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="动作：created/merged/approved/rejected/updated/deleted")
    before_json: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="变更前快照 JSON")
    after_json: Mapped[str | None] = mapped_column(
        TEXT, nullable=True, comment="变更后快照 JSON")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")


class UserMemory(Base):
    """能力类长期记忆明细表（T9.2，L1 的核心结构）。

    为什么单独建表而不是继续用 `user_profiles` 的两个 JSON 数组：
    数组只能表达「会不会」，表达不了**多熟（掌握程度）、依据是什么（来源）、
    有多可信（置信度）、什么时候得出的（证据时间）**——而这四样正是
    「越用越准」和「时间衰减」的前提。JSON 数组里塞不下这些维度。

    一行 = 一个能力条目（一个技能 / 一个薄弱点 / 一条答题方法）。
    L2 的「答题方法」与 L1 的事实共用这张表：两者的差别是**语义**而不是**结构**，
    共用还能让注入逻辑统一（见 T9.10 的讨论）。

    隔离：所有读写都必须带 `user_id`，(user_id, category, name) 唯一，
    同一条记忆不会被重复插入。
    """

    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "name", name="uk_user_memory_entry"),
        Index("idx_user_memories_user_category", "user_id", "category"),
        {"comment": "用户能力类记忆明细表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户 FK（隔离键）")
    # 0=技能 1=薄弱点 2=答题方法（L2）；取值定义见 user_memory_service
    category: Mapped[int] = mapped_column(
        nullable=False, comment="类别：0技能 1薄弱点 2答题方法")
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="条目名，如 'MySQL 索引优化'")
    # 0-100 整数。对外展示时映射成「熟练/熟悉/了解/待加强」四档，不给用户看分数
    mastery: Mapped[int] = mapped_column(
        nullable=False, default=50, server_default="50",
        comment="掌握程度 0-100（越高越熟）")
    # 0=模型推断 1=用户自述 2=简历声明 3=行为证据；权重顺序见 user_memory_service
    source: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0",
        comment="来源：0模型推断 1用户自述 2简历声明 3行为证据")
    confidence: Mapped[int] = mapped_column(
        nullable=False, default=50, server_default="50",
        comment="置信度 0-100")
    evidence_count: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1", comment="被证据强化过几次")
    last_evidence_at: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="最后一次证据时间 Unix 秒（给时间衰减用）")
    # 1=自动抽取待用户确认（T9.9），0=已生效
    pending_approval: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="0已生效 1待用户确认")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="更新时间 Unix 秒",
    )


class InterviewEvaluation(Base):
    """面试复盘结果表（对应 T8.2）。

    为什么单独建表而不是往 `interviews` 加列：`create_all` **不会给已有表加列**
    （要迁移，而 Alembic 现在是空壳，见 T10.7），加列等于要动线上表结构。
    单独建表零风险，而且一场面试的复盘是「一次生成、可能重新生成」的独立结果，
    和面试过程本身分开存也更清楚。

    一场面试一行（`interview_id` 唯一）：重新生成时覆盖，不保留历史版本。
    """

    __tablename__ = "interview_evaluations"
    __table_args__ = (
        Index("idx_interview_evaluations_user", "user_id"),
        {"comment": "面试复盘结果表"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户 FK")
    interview_id: Mapped[int] = mapped_column(
        ForeignKey("interviews.id"),
        unique=True,
        nullable=False,
        comment="面试记录 FK（一场面试一行）",
    )
    summary: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="整体表现总结")
    weak_topics: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, comment="薄弱知识点列表")
    suggestions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, comment="改进建议列表")
    # 复盘来源：0=用面试记录里的问答文本（自动），1=用上传的录音转写（T8.3）。
    # 前端要据此显示「本次复盘来自上传录音」，否则用户不知道这份结论是拿什么评的。
    source: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="来源：0问答文本 1上传录音")
    # 来源为录音时记录对应的资源 ID，便于回放与追查；问答文本复盘时为空。
    resource_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id"), nullable=True, comment="录音资源 FK（仅来源=1）")
    # 生成复盘时的输入规模：问答文本复盘记问答条数，录音复盘记转写出的分句数。
    # 回显时能看出「复盘之后面试记录又变了」（或录音时长不同），据此提示可重新生成。
    qa_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="生成时的问答条数/录音分句数")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="更新时间 Unix 秒",
    )


class SearchDocument(Base):
    """长期记忆 L3 的检索索引（T9.14）。

    为什么单独建一张索引表，而不是给 `chat_messages` / `notes` 加 FULLTEXT：
    加索引同样是 DDL（`create_all` 不会给已有表加索引），而单独建表零风险，
    还能把「对话消息 / 笔记 / 复盘结果」三种来源**统一成一种可检索结构**——
    否则检索逻辑要按来源写三套。

    为什么必须用 **ngram 分词器**：MySQL InnoDB 默认的全文分词按空格与标点切词，
    对中文等于不工作（整句被当成一个词）。`WITH PARSER ngram` 才能按 2 字窗口切分，
    「索引」这种两字词才搜得到。这一条不做的话，检索会在中文场景下静默失效——
    能建索引、能查询、就是搜不到东西。

    检索结果**返回原文**：`content` 存完整文本，不做 LLM 摘要、不截断（Hermes 的明确做法）。
    """

    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_type", "source_id", name="uk_search_document_source"
        ),
        Index("idx_search_documents_user_type", "user_id", "source_type"),
        Index(
            "ft_search_documents_content",
            "title",
            "content",
            mysql_prefix="FULLTEXT",
            mysql_with_parser="ngram",
        ),
        {"comment": "记忆检索索引（L3）"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户 FK（检索范围强制按它过滤）")
    # 0=对话消息 1=笔记 2=面试复盘
    source_type: Mapped[int] = mapped_column(
        nullable=False, comment="来源：0对话消息 1笔记 2面试复盘")
    source_id: Mapped[int] = mapped_column(
        nullable=False, comment="来源记录 ID（无外键：源记录删除后索引由服务显式清理）")
    session_id: Mapped[int | None] = mapped_column(
        nullable=True, comment="所属会话（仅对话消息有）")
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", server_default="", comment="标题/问题")
    content: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="正文（原文，不截断）")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="来源时间 Unix 秒")
    indexed_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="入索引时间 Unix 秒")


class SessionSummary(Base):
    """长会话的上下文摘要（T9.16）。

    **它不属于三层记忆**——对应的是 Hermes 的上下文压缩（`/compress`），
    解决的是「一个会话聊到 50 轮，早期内容被截断掉」这个问题：
    `prompt_layer` 只取最近 N 条原始消息，更早的内容原本就彻底丢了。

    做法是渐进式的：每积累一批未总结的消息就压一次，而不是每次全量重压。
    `covered_message_id` 记录「已经总结到哪条消息」，据此判断增量。
    """

    __tablename__ = "session_summaries"
    __table_args__ = (
        UniqueConstraint("session_id", name="uk_session_summary_session"),
        {"comment": "长会话上下文摘要"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True, comment="用户 FK")
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id"), nullable=False, comment="会话 FK（一个会话一份摘要）")
    summary: Mapped[str] = mapped_column(
        MEDIUMTEXT, nullable=False, comment="早期内容的摘要")
    # 已总结到哪条消息：据此算增量，避免每次都把整段历史重新压一遍
    covered_message_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0",
        comment="已覆盖到的最新消息 ID")
    covered_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0", comment="已覆盖的消息条数")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=_unix_ts,
        onupdate=_unix_ts,
        comment="更新时间 Unix 秒",
    )


class UsageRecord(Base):
    """模型调用用量明细（T12.3）。

    演示环境按 IP 限配额（每个 IP 累计 300 万 token），前提是**每一次模型调用都能记账**，
    所以这张表是一切的账本：谁、哪个 IP、哪个场景、用了多少 token。

    几个刻意的设计：

    1. **`user_id` 不建外键**，只是软引用。这是审核/账本类表的常见做法，好处很实际：
       删除用户时不用再关心这张表的清理顺序——项目里"加新表忘了同步删除顺序导致删用户
       撞外键"已经踩过六次（题库、画像提案、复盘、记忆……），账本表不该再添一次。
       代价是删用户后会留下孤儿账本行，这对审计来说反而是想要的效果。
    2. **记 `reasoning_tokens`**：实测这个模型输出 137 token 里有 133 是推理过程，
       它照样计费。只记正文会严重低估成本，也不利于事后分析。
    3. **记 `client_ip` 与 `app_env`**：配额按 IP 聚合，环境字段用于区分
       （虽然演示与正式是两套库，但报表里能一眼看出数据来自哪套环境）。
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        # 每 IP 累计 token 的聚合查询走这条索引。
        Index("idx_usage_records_ip", "client_ip", "created_at"),
        # 全局每日预算的聚合查询走这条。
        Index("idx_usage_records_created", "created_at"),
        {"comment": "模型调用用量明细（演示环境配额的账本）"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True,
        comment="用户 ID（软引用，不建外键：删用户不该被账本挡住）")
    client_ip: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default="",
        comment="客户端 IP（配额按它聚合）")
    app_env: Mapped[str] = mapped_column(
        String(16), nullable=False, default="", server_default="",
        comment="调用发生的环境：development/demo/test/production")
    scene: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", server_default="",
        comment="业务场景：chat/quiz/evaluation/memory/resume/summary 等")
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", server_default="",
        comment="模型提供方")
    model: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default="",
        comment="模型名")
    prompt_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0",
        comment="输入 token 数")
    completion_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0",
        comment="输出 token 数（含推理）")
    reasoning_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0",
        comment="输出里属于推理过程的部分，同样计费")
    total_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0",
        comment="总 token 数：配额就是按这个值累计的")
    created_at: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=_unix_ts, comment="创建时间 Unix 秒")
