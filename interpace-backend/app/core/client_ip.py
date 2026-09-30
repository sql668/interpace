"""统一获取客户端真实 IP（对应 T12.4）。

配额是按 IP 算的，所以"IP 能不能被伪造"直接决定配额有没有意义。

## 根本区别：TCP 层不可伪造，HTTP 头可以

- `request.client.host`（也就是 Nginx 的 `$remote_addr`）来自 **TCP 连接的对端地址**，
  在建立连接后伪造不了；
- `X-Forwarded-For` / `X-Real-IP` 只是**普通 HTTP 头**，客户端想写什么就写什么。

所以真正可信的只有一个来源：**谁直接连到了我们**。转发头只有在"请求确实来自我们自己的代理"
这个前提下才有意义，这正是 `TRUST_PROXY_HEADERS` 控制的边界。

## 本项目踩过的真实坑

Nginx 原来用的是 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`，
它的语义是「**保留客户端传来的值，在末尾追加真实 IP**」。也就是说 XFF 的**第一个**值
可以被客户端随便伪造，只有**最后一个**是真的。而原来的 `rate_limit.py` 恰好取第一个值——
攻击者每个请求换一个假 XFF，限流就完全失效。

已经在两处修掉：

1. Nginx 改成**覆盖**：`proxy_set_header X-Forwarded-For $remote_addr;`
   （见 `interpace-frontend/deploy/nginx.conf`），后端看到的值永远只有一个；
2. 这里按「不可伪造优先」的顺序取值。

## 取值顺序

1. `X-Real-IP`：Nginx 用 `$remote_addr` 覆盖写入，客户端伪造不了（前提是走我们的 Nginx）；
2. `X-Forwarded-For` 的**最后一段**：兜底。Nginx 已经覆盖写入，正常情况下两者相同；
   保留这段是为了兼容多层代理的部署（那种情况下最靠近我们的那层写的最可信）；
3. 直连时的 `request.client.host`。

这一切只在 `TRUST_PROXY_HEADERS=true` 时才认。直连暴露的服务如果信任这些头，
等于把"我是谁"的决定权交给客户端——所以默认是 `false`，部署到 Nginx 后面才打开。

## 前面还有 CDN 时怎么办

如果以后在 Nginx 前面挂了 CDN / 高防（腾讯云 CDN、Cloudflare 等），`$remote_addr`
会变成 **CDN 节点的 IP**，这时候不能用它，需要在 Nginx 用 `ngx_http_realip_module` 还原：

```nginx
set_real_ip_from 1.2.3.0/24;      # CDN 的回源网段，只信任这些
real_ip_header X-Forwarded-For;   # 从哪个头里取真实 IP（Cloudflare 用 CF-Connecting-IP）
real_ip_recursive on;             # 从右往左跳过受信代理，第一个不可信的就是客户端
```

配好之后 `$remote_addr` 就是真实客户端 IP，上面的覆盖转发会自动正确。
**关键仍然是 `set_real_ip_from` 只列可信网段**——把 `0.0.0.0/0` 写进去等于谁都能伪造。
"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import Request

from app.core.settings import settings

# 拿不到任何信息时的占位符。注意它会让所有这类请求共用同一份配额，
# 这是刻意的保守选择：宁可把匿名流量算在一起，也不要因为"IP 是空的"就放行。
UNKNOWN_CLIENT_IP = "unknown"


def resolve_client_ip_from_headers(
    headers: Mapping[str, str], peer_host: str | None
) -> str:
    """从请求头与直连地址里解析真实客户端 IP。

    抽成独立函数是因为 HTTP 与 WebSocket 都要用：WebSocket 不走 HTTP 中间件、
    拿不到 `Request`，但两者的取值口径必须一致——否则同一个用户从
    HTTP 和 WS 进来会被算成两个 IP，配额各算一份。
    """
    if settings.trust_proxy_headers:
        real_ip = (headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip

        forwarded_for = (headers.get("x-forwarded-for") or "").strip()
        if forwarded_for:
            # 取最后一段：这是我们自己的代理追加进去的真实来源 IP。
            last_hop = forwarded_for.split(",")[-1].strip()
            if last_hop:
                return last_hop

    if peer_host:
        return peer_host
    return UNKNOWN_CLIENT_IP


def resolve_client_ip(request: Request) -> str:
    """按「不可伪造优先」的顺序解析 HTTP 请求的客户端 IP。"""
    peer_host = request.client.host if request.client else None
    return resolve_client_ip_from_headers(request.headers, peer_host)
