# 前端镜像（T11.3）
#
# ⚠️ 重要：这个镜像**必须在本地或 CI 构建**，不要在 2核2G 的服务器上构建。
# `vite build` 峰值内存通常在 1GB 以上（本项目产物较大，见 T10.4），
# 在服务器上和 MySQL 抢内存极容易触发 OOM Killer。服务器只负责 `docker pull` + `up`。
#
# 运行时是 Nginx：既托管 `dist/` 静态文件，也把 `/api` 反代到后端容器，
# 这样浏览器只看到一个同源地址，不需要额外处理 CORS。

# ---------- 构建阶段 ----------
FROM node:22-slim AS builder

# 锁定 pnpm 版本（与开发机一致）。
# 不锁的话 corepack 会装最新版，而 **pnpm 10+ 遇到"被忽略的构建脚本"会直接报错退出**
# （ERR_PNPM_IGNORED_BUILDS），本地用 9.x 构建正常、容器里却失败——
# 这种"环境版本差导致的构建失败"最省事的解法就是把版本钉死。
RUN npm install -g pnpm@9.1.0

WORKDIR /app

# 先装依赖、再拷源码：改业务代码不会让依赖层缓存失效。
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

# 接口基地址用**构建参数**注入并给默认值。
# 不能依赖仓库里的 `.env.production`：那个文件被 .gitignore 排除了，
# 全新克隆（或 CI）里根本没有它，构建出来的产物会缺 VITE_API_BASE_URL，
# 前端一加载就抛"缺少环境变量"——而且是在**用户浏览器里**报，很难定位。
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APP_TITLE=面途 InterPace AI
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_TITLE=${VITE_APP_TITLE}

# 走 .env.production：VITE_API_BASE_URL=/api/v1（同源，由 Nginx 反代）。
RUN pnpm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine AS runtime

# 只带静态产物与一份 Nginx 配置，构建工具链全部留在上一阶段。
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
