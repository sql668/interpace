import threading
import time

from fastapi import Request

from app.core import raise_error
from app.core.client_ip import resolve_client_ip

# 全局锁：保证并发请求下计数更新的原子性
_LOCK = threading.Lock()
# 计数存储：key -> (请求时所在的“时间段的开始时间”, 已经请求了多少次)
_WINDOWS: dict[str, tuple[int, int]] = {}


def rate_limit_dep(limit: int, window_seconds: int, key_prefix: str):
    """内存限流依赖：固定窗口 + IP 维度。

    实现要点：
    1) 以 (key_prefix + 客户端IP) 作为限流键，区分不同接口与客户端。
    2) 固定窗口：把时间划分为 [window_seconds] 秒一段的桶。
    3) 每个桶内最多允许 [limit] 次请求，超出直接返回 429。
    """

    async def dependency(request: Request) -> None:
        # T12.4：改用统一的真实 IP 解析。
        #
        # 原来是直接取 `X-Forwarded-For` 的**第一个**值，而 Nginx 用的是
        # `$proxy_add_x_forwarded_for`——它保留客户端传来的值、把真实 IP 追加在末尾，
        # 所以第一个值可以被客户端随便伪造（每个请求换个假 IP，限流就完全失效）。
        # 现在优先用 Nginx 覆盖写入的 `X-Real-IP`，并且只在 TRUST_PROXY_HEADERS=true 时才认这些头。
        client_host = resolve_client_ip(request)
        key = f"{key_prefix}:{client_host}"
        now = int(time.time())
        # 计算当前时间所在的时间窗口起点（固定窗口）
        window_start = now - (now % window_seconds)
        with _LOCK:
            # 读取当前窗口的起始时间和请求次数，不存在则初始化
            last_start, count = _WINDOWS.get(key, (window_start, 0))
            # 跨窗口则重置计数
            if last_start != window_start:
                last_start, count = window_start, 0
            # 超过限制直接抛错
            if count >= limit:
                raise_error(
                    code=429,
                    message="请求过于频繁，请稍后再试",
                    detail={"limit": limit, "window_seconds": window_seconds},
                )
            # 计数 +1 并写回
            _WINDOWS[key] = (last_start, count + 1)

    return dependency


def reset_rate_limit_windows() -> None:
    """清空所有限流窗口。

    主要给测试用：限流是进程内的固定窗口，同一次 pytest 里跑多个用例时，
    它们共用同一个「客户端 IP」键，注册次数很容易超过每分钟 5 次而互相拖累。
    测试在用例开始前调用本函数即可让每个用例从零计数。
    """
    with _LOCK:
        _WINDOWS.clear()
