"""上线冒烟检查（T11.8）：在已部署的实例上跑一遍关键链路。

为什么做成脚本而不是纸面清单：纸面清单每次靠人照着敲 curl，步骤一多就会漏、也会抄错。
脚本能重复跑、失败会非零退出，可以直接塞进部署流程当门禁。

**跑在容器里**（`docker compose exec backend python /app/scripts/smoke_test.py`），原因有二：

1. 服务器上不一定装了 python3，而后端镜像里本来就有 httpx，零额外依赖；
2. 默认基地址是 `http://frontend/api/v1`（compose 里的服务名），于是这条链路
   **真的经过了 Nginx 反代**——那才是生产环境实际走的路径。直接打 `127.0.0.1:8000`
   会绕过 Nginx，把 SSE 缓冲、反代配置这类问题全漏掉。

**关于"模型相关的结果"**：出题能不能生成卷子、简历能不能导出 Word，取决于模型这一轮
吐出来的内容，不是确定性的。所以脚本只断言**链路通不通**（接口可达、流式有响应、
数据落了库），模型产物只打印摘要、不做断言——否则模型心情不好就会把冒烟测试判成失败，
久而久之就没人信它了。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from typing import Any

import httpx

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


class SmokeTest:
    def __init__(self, base_url: str, health_base: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.health_base = health_base.rstrip("/")
        self.timeout = timeout
        self.failures: list[str] = []
        self.token = ""
        self.session_id = 0
        self.message_id: int | None = None

    # ---------- 工具 ----------

    def client(self) -> httpx.Client:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        return httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers)

    def step(self, name: str, ok: bool, detail: str = "") -> bool:
        mark = f"{GREEN}  OK  {RESET}" if ok else f"{RED} FAIL {RESET}"
        print(f"[{mark}] {name}{('  ' + detail) if detail else ''}")
        if not ok:
            self.failures.append(name)
        return ok

    def note(self, text: str) -> None:
        print(f"         └─ {text}")

    # ---------- 各步骤 ----------

    def check_health(self) -> bool:
        """探活接口**不带 /api/v1 前缀**（T10.1）。"""
        ok = True
        for path in ("/health/live", "/health/ready"):
            try:
                resp = httpx.get(self.health_base + path, timeout=10)
                ok = self.step(f"探活 {path}", resp.status_code == 200, f"-> {resp.status_code}") and ok
            except Exception as exc:  # noqa: BLE001
                ok = self.step(f"探活 {path}", False, f"-> {exc!r}") and ok
        return ok

    def check_runtime_config(self) -> bool:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.get("/config/runtime")
        if not self.step("运行时配置 /config/runtime", resp.status_code == 200, f"-> {resp.status_code}"):
            return False
        body = resp.json()
        features = body.get("features") or {}
        self.note(
            f"环境={body.get('app_env')} 配额生效={body.get('quota_enforced')} "
            f"语音={features.get('voice_interview')} 附件={features.get('file_upload')} "
            f"面试上限={body.get('interview_max_minutes')}分钟"
        )
        return True

    def register_and_login(self) -> bool:
        username = f"smoke_{uuid.uuid4().hex[:8]}"
        password = "smoke123456"
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            register = client.post("/auth/register", json={"username": username, "password": password})
            if not self.step("注册", register.status_code == 201, f"-> {register.status_code} {_short(register)}"):
                return False
            login = client.post("/auth/login", json={"username": username, "password": password})
            if not self.step("登录", login.status_code == 200, f"-> {login.status_code} {_short(login)}"):
                return False
            self.token = login.json()["access_token"]
            # 顺带确认这个 token 真能用（而不是只返回了一串字符）
            probe = client.get("/users", headers={"Authorization": f"Bearer {self.token}"})
        return self.step("用 token 访问受保护接口", probe.status_code == 200, f"-> {probe.status_code}")

    def create_session(self) -> bool:
        with self.client() as client:
            resp = client.post("/sessions", json={"title": "上线冒烟", "session_model": 0})
        if not self.step("创建会话", resp.status_code == 200, f"-> {resp.status_code} {_short(resp)}"):
            return False
        self.session_id = int(resp.json()["session"]["id"])
        self.note(f"session_id={self.session_id}")
        return True

    def upload_attachment(self) -> int | None:
        content = (
            "个人简历\n姓名：张三\n求职意向：后端开发工程师\n"
            "项目经历：负责订单系统，用定时任务扫描超时未支付订单并关闭。\n"
        ).encode()
        with self.client() as client:
            resp = client.post(
                "/upload/file",
                files={"file": ("smoke-resume.txt", content, "text/plain")},
                data={"storage_scene": "0", "upload_purpose": "0"},
            )
        if resp.status_code == 403:
            # 演示环境可能刻意关掉上传（T12.5）：不算失败，但要说明后面跳过了什么
            self.note("附件上传被配置关闭（features.file_upload=false），跳过上传相关步骤")
            return None
        if not self.step("上传附件", resp.status_code == 201, f"-> {resp.status_code} {_short(resp)}"):
            return None
        body = resp.json()
        self.note(f"resource_id={body['resource_id']} 解析={(body.get('parse') or {}).get('message', '-')}")
        # 取回内容：验证对象存储（MinIO）真的能读回来。
        # 只测"上传返回 201"是不够的——写入成功但读不回来是常见的半通状态。
        with self.client() as client:
            fetched = client.get(f"/resources/{body['resource_id']}/content")
        self.step(
            "读回附件内容（验证对象存储）",
            fetched.status_code == 200 and fetched.content == content,
            f"-> {fetched.status_code} {len(fetched.content)} 字节",
        )
        return int(body["resource_id"])

    def stream_chat(self, resource_id: int | None) -> bool:
        payload: dict[str, Any] = {"request_text": "用一句话解释什么是索引", "select_model": 0}
        if resource_id:
            payload["segments"] = [
                {"type": "file", "name": "smoke-resume.txt", "resource_id": resource_id}
            ]

        events: list[dict[str, Any]] = []
        started = time.monotonic()
        with self.client() as client:
            with client.stream(
                "POST",
                f"/sessions/{self.session_id}/stream-chat?session_model=0",
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    return self.step("流式对话（SSE）", False, f"-> {resp.status_code} {_short(resp)}")
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        continue
        elapsed = time.monotonic() - started

        kinds = [event.get("type") for event in events]
        done = next((e for e in events if e.get("type") == "done"), None)
        start = next((e for e in events if e.get("type") == "start"), None)
        if start:
            # 停止接口要的是消息 id，它只在 start 事件里
            self.message_id = start.get("message_id")

        ok = self.step(
            "流式对话（SSE：start + delta + done）",
            "start" in kinds and "delta" in kinds and done is not None,
            f"-> {len(events)} 个事件 / {elapsed:.1f}s",
        )
        if done:
            text = done.get("response_text") or ""
            self.note(f"回答 {len(text)} 字：{text[:40]}…")
        return ok

    def stop_stream(self) -> bool:
        """停止接口是幂等的：流已经自然结束时再调一次也必须成功（T1.8）。"""
        if not self.message_id:
            return self.step("停止流式回答（幂等）", False, "-> 没拿到 message_id")
        with self.client() as client:
            resp = client.post(
                f"/sessions/{self.session_id}/stream-chat/stop",
                json={"message_id": self.message_id},
            )
        return self.step("停止流式回答（幂等）", resp.status_code == 200, f"-> {resp.status_code}")

    def check_persistence(self) -> bool:
        """消息要真的落库，而不是只推给前端就完了。"""
        with self.client() as client:
            resp = client.get(f"/sessions/{self.session_id}/messages?session_model=0")
        if not self.step("读回消息列表", resp.status_code == 200, f"-> {resp.status_code}"):
            return False
        messages = resp.json().get("messages") or []
        answered = [m for m in messages if (m.get("response_text") or "").strip()]
        self.note(f"{len(messages)} 条消息，其中 {len(answered)} 条有回答正文")
        return self.step("回答已落库", bool(answered))

    def check_business_endpoints(self) -> bool:
        """业务接口可达性。返回内容取决于模型，所以只断言接口通、不断言内容。"""
        checks = [
            ("会话列表", "/sessions?session_model=0"),
            ("题库列表", f"/quiz-papers?session_id={self.session_id}"),
            ("我的画像", "/profile"),
            ("记忆列表", "/profile/memories"),
            ("记忆变更日志", "/profile/memory-logs"),
            ("笔记列表", "/notes"),
            ("检索", "/search?q=索引"),
        ]
        ok = True
        with self.client() as client:
            for name, path in checks:
                try:
                    resp = client.get(path)
                except Exception as exc:  # noqa: BLE001
                    ok = self.step(name, False, f"-> {exc!r}") and ok
                    continue
                ok = self.step(name, resp.status_code == 200, f"-> {resp.status_code}") and ok
        return ok

    def cleanup(self) -> None:
        """清掉冒烟产生的数据，不给对方留垃圾。"""
        with self.client() as client:
            resp = client.delete(f"/sessions/{self.session_id}?session_model=0")
        self.step("删除冒烟会话（清理）", resp.status_code == 200, f"-> {resp.status_code}")


def _short(resp: httpx.Response) -> str:
    try:
        return str(resp.json())[:110]
    except Exception:  # noqa: BLE001
        return resp.text[:110]


def main() -> int:
    parser = argparse.ArgumentParser(description="面途上线冒烟检查")
    parser.add_argument(
        "--base-url",
        default="http://frontend/api/v1",
        help="业务接口基地址（默认走 compose 里的 Nginx，才能覆盖反代那条路径）",
    )
    parser.add_argument(
        "--health-base",
        default="http://frontend",
        help="探活接口基地址（探活本身不带 /api/v1 前缀）",
    )
    args = parser.parse_args()

    print("=" * 72)
    print(f"面途上线冒烟检查：{args.base_url}")
    print("=" * 72)

    test = SmokeTest(args.base_url, args.health_base)

    # 前置步骤失败就没必要往下跑了：后面每一步都依赖登录拿到的 token
    for step in (test.check_health, test.check_runtime_config, test.register_and_login, test.create_session):
        if not step():
            print(f"\n{RED}关键前置步骤失败，后续检查跳过。{RESET}")
            return 1

    resource_id = test.upload_attachment()
    test.stream_chat(resource_id)
    test.stop_stream()
    test.check_persistence()
    test.check_business_endpoints()
    test.cleanup()

    print("-" * 72)
    if test.failures:
        print(f"结果：{RED}{len(test.failures)} 项失败{RESET} -> {', '.join(test.failures)}")
        return 1
    print(f"结果：{GREEN}全部通过{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
