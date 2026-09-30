"""应用配置：从分层 .env 与操作系统环境变量加载，供全局单例 `settings` 使用。"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
# 直接使用 loguru 的 logger，而不是项目的 main_logger：logging_config 依赖本模块，
# 反向导入会形成循环。此处只是启动期的一行诊断，日志配置尚未生效也不影响可用性。
from loguru import logger


# 支持的运行环境（T12.1）。四档对应四套 `.env.{env}`：
# development=本机开发，demo=对外演示（有配额），test=测试，production=正式。
VALID_APP_ENVS = ("development", "demo", "test", "production")

# 常见简写别名，避免因为它们直接启动失败——这类写法在部署脚本里很常见。
_APP_ENV_ALIASES = {
    "dev": "development",
    "prod": "production",
    "staging": "test",
}


def _normalize_app_env(raw_env: str | None) -> str:
    """归一 `APP_ENV`；**无法识别的值直接报错**。

    原来的实现把任何不认识的取值都归到 `development`，这是一次**静默降级**：
    部署时把 `APP_ENV` 写错（例如 `demoo`、`Demoo `）会安静地按开发环境跑起来，
    配额、日志级别、生产专用分支全部失效，而且没有任何提示——
    对演示环境来说这是最危险的一种错：以为配额开着，其实一点没生效。
    """
    env = (raw_env or "").strip().lower()
    if not env:
        return "development"
    env = _APP_ENV_ALIASES.get(env, env)
    if env not in VALID_APP_ENVS:
        raise RuntimeError(
            f"无法识别的 APP_ENV={raw_env!r}，可选值：{' / '.join(VALID_APP_ENVS)}"
            f"（也接受 {' / '.join(sorted(_APP_ENV_ALIASES))} 这些简写）"
        )
    return env


def _project_root() -> Path:
    """返回后端项目根目录（`app` 的上一级，用于定位 `.env.*` 文件）。"""
    return Path(__file__).resolve().parents[2]


def _load_layered_env() -> tuple[str, dict[str, Any]]:
    """
    读取 `项目根/.env.{app_env}` 并与 `os.environ` 合并（后者覆盖文件中的同名键）。

    返回: (标准化后的 app_env, 合并后的键值对)
    """
    app_env = _normalize_app_env(os.getenv("APP_ENV", "development"))
    logger.info(f"Loading environment for APP_ENV={app_env} ...")
    root = _project_root()
    env_values = dotenv_values(root / f".env.{app_env}")
    merged = {**env_values, **os.environ}
    return app_env, merged


# JWT 密钥的最小字节数（RFC 7518 §3.2 对 HS256 的建议）。低于它的密钥签名强度不足，
# 而且 PyJWT 只会打一条 InsecureKeyLengthWarning——不主动校验就会被忽略（真发生过）。
MIN_JWT_SECRET_BYTES = 32

# CORS 白名单的默认值：本机开发时前端跑在 8080（vite 代理）或 5173（vite 直连）。
# 生产环境**同源部署**（Nginx 同时托管前端与反代 /api），根本不会触发 CORS，
# 所以这个默认值不会被用到；只有前后端分域部署时才需要配 CORS_ORIGINS。
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True)
class Settings:
    """
    不可变应用配置。通过 `from_env` 从环境构建；字段与 `.env` / 启动环境变量名对应见各字段注释。

    必填项在 `from_env` 内显式校验：MYSQL_URL、JWT_SECRET、MinIO 四元组等。
    """

    app_env: str  # 运行环境：development / demo / test / production（见 VALID_APP_ENVS）
    mysql_url: str  # SQLAlchemy 风格数据库连接串（如 mysql+pymysql://...）
    trust_proxy_headers: bool  # 是否信任 X-Real-IP / X-Forwarded-For（部署在 Nginx 后面时为 true）
    cors_origins: tuple[str, ...]  # 允许跨域访问的来源；同源部署时用不到
    jwt_secret: str  # JWT 签名密钥
    jwt_algorithm: str  # JWT 算法，如 HS256
    jwt_access_expire_minutes: int  # Access Token 有效时长（分钟）
    jwt_refresh_expire_minutes: int  # Refresh Token 有效时长（分钟）
    minio_endpoint: str  # MinIO 服务地址（host:port，无协议）
    minio_access_key: str  # MinIO 访问 Key
    minio_secret_key: str  # MinIO 访问 Secret
    minio_bucket: str  # 默认存储桶名
    minio_secure: bool  # 是否对 MinIO 使用 HTTPS
    deepseek_api_key: str  # 兼容 OpenAI 接口的 API Key（如 DeepSeek），流式聊天必填
    deepseek_base_url: str  # 兼容 OpenAI 的 API Base URL
    deepseek_model: str  # 模型名，如 deepseek-chat
    deepseek_temperature: float  # 采样温度
    deepseek_max_tokens: int  # 单次补全最大 token 数
    redis_host: str  # Redis 服务器地址
    redis_port: int  # Redis 服务器端口
    redis_db: int  # Redis 数据库编号
    redis_password: str  # Redis 密码
    volc_api_key: str  # 火山引擎语音服务 API Key（ASR 与 TTS 共用），模拟面试语音必填
    volc_asr_resource_id: str  # ASR 模型版本，如 volc.seedasr.sauc.duration
    volc_tts_resource_id: str  # TTS 模型版本，如 seed-tts-2.0
    volc_tts_speaker: str  # TTS 音色 ID（控制台音色库获取）
    volc_asr_url: str  # ASR WebSocket 接入点
    volc_tts_url: str  # TTS WebSocket 接入点
    volc_asr_file_url: str  # ASR 整段识别接入点（上传录音用，不等实时节拍）

    @staticmethod
    def from_env() -> "Settings":
        """
        从分层 env 与 `os.environ` 解析出 `Settings` 实例；缺必填项时抛出 `RuntimeError`。
        大模型相关项允许为空 Key（调用模型时再失败），与 MinIO/JWT/DB 策略不同处见代码分支。
        """
        app_env, values = _load_layered_env()

        mysql_url = str(values.get("MYSQL_URL", "")).strip()
        if not mysql_url:
            raise RuntimeError("Environment variable MYSQL_URL is required")

        jwt_secret = str(values.get("JWT_SECRET", "")).strip()
        if not jwt_secret:
            raise RuntimeError("Environment variable JWT_SECRET is required")
        # T10.6：HS256 的密钥长度下限（RFC 7518 §3.2 建议 32 字节）。
        # 放在这里校验是为了**让配置错误在启动时就暴露**——否则运行期只会打一条
        # InsecureKeyLengthWarning，很容易被忽略过去（原来 20 字节的密钥就是这么留下来的）。
        if len(jwt_secret.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            raise RuntimeError(
                f"JWT_SECRET 至少需要 {MIN_JWT_SECRET_BYTES} 字节"
                f"（当前 {len(jwt_secret.encode('utf-8'))} 字节）。"
                f"生成方式：python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

        minio_endpoint = str(values.get("MINIO_ENDPOINT", "127.0.0.1:9000")).strip()
        minio_access_key = str(values.get("MINIO_ACCESS_KEY", "minioadmin")).strip()
        minio_secret_key = str(values.get("MINIO_SECRET_KEY", "minioadmin")).strip()
        minio_bucket = str(values.get("MINIO_BUCKET", "ai-resources")).strip()
        if not minio_endpoint or not minio_access_key or not minio_secret_key or not minio_bucket:
            raise RuntimeError("MinIO config is incomplete")

        deepseek_api_key = str(values.get("DEEPSEEK_API_KEY", "")).strip()
        deepseek_base_url = str(values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).strip()
        deepseek_model = str(values.get("DEEPSEEK_MODEL", "deepseek-chat")).strip()
        deepseek_temperature = float(values.get("DEEPSEEK_TEMPERATURE", 0.7))
        deepseek_max_tokens = int(values.get("DEEPSEEK_MAX_TOKENS", 1024))

        return Settings(
            app_env=app_env,
            mysql_url=mysql_url,
            # T12.4：配额按 IP 计算，而 IP 的可信度取决于"是不是部署在反向代理后面"。
            # 默认 false（安全）：直连暴露的服务如果信任 X-Forwarded-For，
            # 任何人都能伪造 IP 绕过配额。部署到 Nginx 后面时在 .env 里打开。
            trust_proxy_headers=str(
                values.get("TRUST_PROXY_HEADERS", "false")
            ).strip().lower()
            == "true",
            # 逗号分隔，例如 CORS_ORIGINS=https://a.com,https://b.com。
            # 空值 = 用默认的开发地址（默认值里都是 localhost，公网请求本来就带不上）。
            cors_origins=tuple(
                origin.strip()
                for origin in str(values.get("CORS_ORIGINS", "")).split(",")
                if origin.strip()
            )
            or _DEFAULT_CORS_ORIGINS,
            jwt_secret=jwt_secret,
            jwt_algorithm=str(values.get("JWT_ALGORITHM", "HS256")),
            jwt_access_expire_minutes=int(values.get("JWT_ACCESS_EXPIRE_MINUTES", 30)),
            jwt_refresh_expire_minutes=int(values.get("JWT_REFRESH_EXPIRE_MINUTES", 10080)),
            minio_endpoint=minio_endpoint,
            minio_access_key=minio_access_key,
            minio_secret_key=minio_secret_key,
            minio_bucket=minio_bucket,
            minio_secure=str(values.get("MINIO_SECURE", "false")).strip().lower() == "true",
            deepseek_api_key=deepseek_api_key,
            deepseek_base_url=deepseek_base_url,
            deepseek_model=deepseek_model,
            deepseek_temperature=deepseek_temperature,
            deepseek_max_tokens=deepseek_max_tokens,
        redis_host=str(values.get("REDIS_HOST", "127.0.0.1")).strip(),
        redis_port=int(values.get("REDIS_PORT", 6379)),
        redis_db=int(values.get("REDIS_DB", 0)),
        redis_password=str(values.get("REDIS_PASSWORD", "")).strip(),
        # 语音相关：允许为空 Key（与 deepseek 同样的策略，真正调用时再失败），
        # 这样没配语音的开发环境照样能启动、照样能跑不需要语音的功能。
        volc_api_key=str(values.get("VOLC_API_KEY", "")).strip(),
        volc_asr_resource_id=str(
            values.get("VOLC_ASR_RESOURCE_ID", "volc.seedasr.sauc.duration")
        ).strip(),
        volc_tts_resource_id=str(
            values.get("VOLC_TTS_RESOURCE_ID", "seed-tts-2.0")
        ).strip(),
        volc_tts_speaker=str(
            values.get("VOLC_TTS_SPEAKER", "zh_female_vv_uranus_bigtts")
        ).strip(),
        volc_asr_url=str(
            values.get(
                "VOLC_ASR_URL",
                "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
            )
        ).strip(),
        volc_tts_url=str(
            values.get(
                "VOLC_TTS_URL",
                "wss://openspeech.bytedance.com/api/v3/tts/bidirection",
            )
        ).strip(),
        # 上传录音走「整段识别」端点：服务端尽快跑完，不像流式那样必须按实时节拍喂音频。
        # 实测 14.4 秒音频约 2.4 秒出结果（流式端点按官方要求要实时发，同样音频要 14 秒）。
        volc_asr_file_url=str(
            values.get(
                "VOLC_ASR_FILE_URL",
                "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream",
            )
        ).strip(),
    )


# 进程级单例：import 时即按当前 APP_ENV 加载
settings = Settings.from_env()
