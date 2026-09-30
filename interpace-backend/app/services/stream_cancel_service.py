"""流式对话的停止登记表（进程内）。

用户点「停止」时，前端先调停止接口登记取消标志，SSE 生成器在循环里轮询这个标志，
命中后立刻跳出，不再消费模型输出、也不做后置处理。

为什么不能只靠前端断连：生成器是同步函数，Starlette 在线程池里迭代它，
客户端断连时的取消不一定能及时打断，也可能跳过 finally 导致已生成内容不落库。
所以用「显式停止接口 + 断连」双保险。

局限：这是进程内状态。当前是单进程部署，够用；如果以后上多 worker，
停止请求可能落到另一个进程上，那时需要换成 Redis 之类的共享存储。
"""

import threading
from collections import OrderedDict

# 登记表容量上限，防止长时间运行后无限增长。
# 登记项不主动清理：保留下来才能让「重复停止」的反馈准确
# （同一 message_id 第二次请求会返回 first_request=false）。
# message_id 自增不复用，所以残留的标志不会影响后续消息。
MAX_CANCEL_ENTRIES = 10_000


class StreamCancelRegistry:
    """`message_id -> 是否已被请求停止` 的线程安全登记表。"""

    def __init__(self, max_entries: int = MAX_CANCEL_ENTRIES) -> None:
        self._cancelled: OrderedDict[int, bool] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries

    def request_cancel(self, message_id: int) -> bool:
        """登记停止请求，返回本次调用是否为首次登记（用于幂等反馈）。"""
        with self._lock:
            first_time = message_id not in self._cancelled
            self._cancelled[message_id] = True
            self._cancelled.move_to_end(message_id)
            while len(self._cancelled) > self._max_entries:
                self._cancelled.popitem(last=False)
            return first_time

    def is_cancelled(self, message_id: int) -> bool:
        """查询是否已登记停止。"""
        with self._lock:
            return self._cancelled.get(message_id, False)


stream_cancel_registry = StreamCancelRegistry()
