"""简历导出服务：把「优化后的简历」段落生成 Word 并落成资源。

对应 T6.4（决策 D12：**先落资源再返回下载地址**，复用现有资源治理与过期回收）。

依赖取舍见 D7：复用已经装好的 `python-docx`，不额外引入依赖。

为什么不直接返回文件流：落资源后前端拿 `resource_id` 走既有的
`GET /resources/{id}/content`（T3.4 已验证），鉴权、下载与过期回收都是现成的；
返回文件流则要另写一套下载与清理。
"""

import re
from io import BytesIO

from docx import Document
from docx.shared import Pt
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import ChatMessage, Resource, User
from app.services.upload_service_minio import UploadService

# 优化后简历所在的小节标题（与 T6.3 的模板约定一致）。
RESUME_SECTION_TITLE = "优化后的简历"

# 「优化后的简历」的兄弟小节：碰到它们说明这一节结束了。
# 不用「遇到标题就结束」的原因：简历正文自己会带 `# 张伟`、`## 技能` 这类标题，
# 用标题级别判断会把正文第一行就当成小节结束（实测踩过），所以只认这几个已知标题。
_SIBLING_SECTION_TITLES = ("简历诊断", "亮点", "不足", "改进建议", "下一步")

# 导出的 Word 文档类型（前端下载时用得上）。
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_ORDERED_RE = re.compile(r"^\s*\d+[.、)]\s+(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def extract_resume_section(text: str) -> str:
    """从整段回答里取出「## 优化后的简历」这一节；取不到就退回全文。

    为什么按小节取：T6.3 的正文是六节结构，用户要下载的是第 5 节，
    把「不足」「改进建议」一起塞进 Word 里没有意义。
    """
    lines = (text or "").splitlines()
    collected: list[str] = []
    inside = False

    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            title = heading.group(2).strip()
            if inside:
                # 碰到兄弟小节才结束；简历正文自己的标题（如 `# 张伟`）不算
                if any(title.startswith(name) for name in _SIBLING_SECTION_TITLES):
                    break
            if RESUME_SECTION_TITLE in title:
                inside = True
                continue
        if inside:
            collected.append(line)

    section = "\n".join(collected).strip()
    if section:
        return section
    # 兜底：模型没按小节输出时，至少别让用户下载不到东西
    return (text or "").strip()


def _add_inline_runs(paragraph, text: str) -> None:
    """把 `**加粗**` 拆成多个 run，其余部分保持普通文本。"""
    cursor = 0
    for match in _BOLD_RE.finditer(text):
        if match.start() > cursor:
            paragraph.add_run(text[cursor : match.start()])
        run = paragraph.add_run(match.group(1))
        run.bold = True
        cursor = match.end()
    if cursor < len(text):
        paragraph.add_run(text[cursor:])


def build_resume_docx(title: str, content: str) -> bytes:
    """把 Markdown 风格的简历文本转成 `.docx` 字节。

    只处理标题、无序 / 有序列表与 `**加粗**`——这是优化后简历实际会出现的结构。
    目标是把内容完整、可读地落进 Word，而不是做一个完整的 Markdown 渲染器。
    """
    document = Document()
    # 正文默认字号调小一档，简历塞得下更多内容。
    document.styles["Normal"].font.size = Pt(10.5)

    if title.strip():
        document.add_heading(title.strip(), level=0)

    for raw_line in (content or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = min(len(heading.group(1)), 4)
            document.add_heading(heading.group(2).strip(), level=level)
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            _add_inline_runs(document.add_paragraph(style="List Bullet"), bullet.group(1))
            continue

        ordered = _ORDERED_RE.match(line)
        if ordered:
            _add_inline_runs(document.add_paragraph(style="List Number"), ordered.group(1))
            continue

        _add_inline_runs(document.add_paragraph(), line.strip())

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class ResumeExportService:
    """导出入口：取消息正文 → 生成 Word → 落资源。"""

    @staticmethod
    def export_from_message(
        db: Session, *, user: User, message_id: int
    ) -> tuple[Resource, bool]:
        """把某条助手消息里的「优化后的简历」导出成 Word 资源。

        返回 (resource, 是否复用已有资源)。
        """
        message = db.get(ChatMessage, message_id)
        # 越权与不存在一律 404，口径与其它接口一致。
        if message is None or message.user_id != user.id:
            raise_error(code=404, message="消息不存在")

        content = extract_resume_section(message.response_text or "")
        if not content.strip():
            raise_error(code=409, message="这条消息里没有可导出的简历内容")

        title = ResumeExportService._build_file_stem(message)
        docx_bytes = build_resume_docx("优化后的简历", content)

        resource, reused = UploadService.save_generated_file(
            db=db,
            user=user,
            file_name=f"{title}.docx",
            data=docx_bytes,
            content_type=DOCX_CONTENT_TYPE,
        )
        main_logger.info(
            f"[简历导出] message_id={message_id} resource_id={resource.id} "
            f"复用={reused} 字节数={len(docx_bytes)}"
        )
        return resource, reused

    @staticmethod
    def _build_file_stem(message: ChatMessage) -> str:
        """文件名去掉非法字符，并带上消息 ID 避免同名混淆。"""
        raw = (message.request_text or "").strip().splitlines()
        head = raw[0].strip() if raw else ""
        safe = re.sub(r'[\\/:*?"<>|\s]+', "-", head)[:30].strip("-")
        return f"简历-{safe}" if safe else f"简历-{message.id}"
