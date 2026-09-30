# Docker 部署

对应 `docs/TODO.md` 的阶段 11。目标机器：**腾讯轻量云 2 核 2G**。

## 三条硬约束（先看这个，后面的每个取舍都源于它）

1. **不在服务器上构建前端**。`vite build` 峰值内存常在 1GB 以上，和 MySQL 抢内存极易 OOM。
   镜像在**本机或 CI** 构建好，服务器只负责 `pull`（或 `docker load`）和 `up`。
2. **后端只跑 1 个 uvicorn worker**。单进程已加载 `pymupdf` 等原生库，2 核多 worker 只会互相抢内存。
   这条写死在镜像的 `CMD` 里，不给环境变量留口子。
3. **常驻内存要留出 ≥300MB 余量**，否则一次大文件解析就可能被 OOM Killer 干掉。

实测各容器常驻内存（空闲状态，见 T11.5）：

| 容器 | 内存 |
| --- | --- |
| frontend (Nginx) | 9 MiB |
| redis | 17 MiB |
| minio | 87 MiB |
| mysql | 155 MiB |
| backend | 245 MiB |
| **合计** | **约 513 MiB** |

2G 机器上跑完这些还剩约 1.2G，余量充足。

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 编排：mysql / redis / minio / backend / frontend |
| `docker-compose.npm.yml` | 叠加文件：服务器上已有 Nginx Proxy Manager 时用（见对应章节） |
| `.env.example` | compose 用的变量模板，**复制成 `.env`** 后填值 |
| `interpace-backend/Dockerfile` | 后端两阶段构建（uv 装依赖，非 root 运行） |
| `interpace-backend/docker-entrypoint.sh` | 启动前跑 `alembic upgrade head`，再 exec uvicorn |
| `interpace-frontend/Dockerfile` | 前端两阶段构建（pnpm 构建 → Nginx 托管） |
| `interpace-frontend/deploy/nginx.conf` | 静态托管 + `/api` 反代（含 SSE 关缓冲、WebSocket 升级头） |
| `interpace-backend/config/demo_limits.json` | 演示环境配额（compose 会把整个 `config/` 打进镜像） |

## 首次部署

```bash
# 1. 准备变量文件（compose 只自动读 .env 这个名字，别改成别的）
cp .env.example .env
vim .env            # 填 MySQL/MinIO 密码、JWT_SECRET、模型 Key

# 2. 先看一眼第三章的架构要求（构建机与服务端 CPU 架构必须一致），
#    再决定是"在服务器上构建"还是"离线传镜像"

# 3. 构建并启动（在服务器上构建时）
docker compose build
docker compose up -d

# 4. 看状态：全部 healthy 才算成功
docker compose ps
```

> 关于约束 1（"不在服务器上构建前端"）：这条针对的是**内存**——vite 峰值约 1GB。
> 但如果你和我一样用 arm64 Mac，在本地构建又会撞上架构问题（见下一节）。
> 两者权衡后，**2核2G 上"在服务器上构建"是可行的**，前提是先加 swap、并且
> **先 build 再 up**（构建时别跑着 MySQL 等）。有 amd64 的构建机或 CI 时，仍推荐离线传输。

## ⚠️ 先确认：构建机和服务器的 CPU 架构必须一致

**这是最容易踩、而且只有到服务器上才会暴露的一脚。** 真机报错长这样：

```
! minio    The requested image's platform (linux/arm64) does not match the detected host platform (linux/amd64/v3)
! redis    The requested image's platform (linux/arm64/v8) does not match the detected host platform (linux/amd64/v3)
! backend  The requested image's platform (linux/arm64) does not match the detected host platform (linux/amd64/v3)
dependency failed to start: container interpace-redis-1 is unhealthy
```

原因：在 Apple Silicon（arm64）Mac 上构建并 `docker save` 出来的镜像是 **arm64** 的，
而云服务器是 amd64，根本跑不起来。（当初那套"离线传输"流程是在同一台 Mac 上验证的，
所以完全没暴露这个问题——**验证环境和目标环境不一致时，验证等于没做**。）

实测（M1 Pro，Apple Silicon）：

| 想产出 amd64 镜像 | 能否在 arm64 Mac 上交叉构建 | 说明 |
| --- | --- | --- |
| 前端镜像（node + vite） | ✅ 可以 | node 在 QEMU 下正常，实测产出 `amd64/linux`，约 90 秒 |
| **后端镜像（`uv sync`）** | ❌ **不行** | `uv` 是 Rust 二进制，QEMU 下直接段错误：`qemu: uncaught target signal 11 (Segmentation fault)` |
| python / node / nginx 的 amd64 变体 | ✅ 能跑 | 说明问题只出在 `uv` 这个二进制上 |
| `mysql:8.0` / `redis:7-alpine` 的 amd64 变体 | ✅ 能拉（加 `--platform linux/amd64`） | |
| `quay.io/minio/minio` 的 amd64 变体 | ❌ 匿名拉取被拒 | 需要 quay 登录 |

**结论：在 arm64 Mac 上无法完整产出 amd64 部署镜像。** 所以推荐流程改成"在服务器上构建"。

## 推荐流程：在服务器上构建

服务器本身就是 amd64，原生构建没有架构问题，也不需要传镜像包。
**源码走 git**：本机 push、服务器 clone / pull —— 后续更新只要一条 `git pull`。

### 首次部署

```bash
# ---- 本机：先确认部署相关文件都提交了 ----
git status --short          # 应该是空的（或者只剩你没打算提交的东西）
git add -A && git commit -m "部署配置" && git push

# 快速自检：这些文件必须在版本控制里，否则服务器 clone 下来会缺东西
git ls-files | grep -E "Dockerfile|docker-compose|docker-entrypoint|\.dockerignore|\.env\.example"

# ---- 服务器：clone ----
mkdir -p /opt && cd /opt
git clone <仓库地址> interpace
cd /opt/interpace

# ---- 配置：.env 不在仓库里，必须手建 ----
cp .env.example .env
vim .env                    # 填 MySQL/MinIO 密码、JWT_SECRET、模型 Key
```

> **`.env` 永远不会从 git 来**（已被 `.gitignore` 排除，这是对的——它装的是密钥）。
> 所以每次换机器都要手动建一份。忘了这步的表现是：
> `MYSQL_ROOT_PASSWORD is missing a value`。

```bash
# ---- 服务器：准备镜像与启动 ----
# 三个第三方镜像必须是对架构的。如果服务器上已有就直接用（compose 不会重复拉）；
# MinIO 的地址按上一节挑一个能拉到的源，必要时写进 .env 的 MINIO_IMAGE
docker image ls | grep -E "mysql|redis|minio"
docker pull mysql:8.0
docker pull redis:7-alpine
docker pull minio/minio:latest        # 拉不到就 docker login quay.io 再拉 quay.io/minio/minio:latest

# 自检架构（必须是 amd64）
docker image inspect mysql:8.0 redis:7-alpine minio/minio:latest --format '{{.RepoTags}} {{.Architecture}}'

# 先构建、再启动：构建期间不跑数据服务，能省下几百 MB 内存（2核2G 上很关键）
docker compose build
docker compose up -d
docker compose ps
```

### 后续更新

```bash
# ---- 本机 ----
git add -A && git commit -m "..." && git push

# ---- 服务器 ----
cd /opt/interpace

# 省事的技巧：把"要叠加的 compose 文件"写进环境变量，
# 之后所有 docker compose 命令都不用再写一长串 -f（接 NPM 的场景特别需要）
export COMPOSE_FILE=docker-compose.yml:docker-compose.npm.yml
# 想每次登录都生效就写进 ~/.bashrc：echo 'export COMPOSE_FILE=...' >> ~/.bashrc

git pull                          # 拉代码
docker compose build              # 重建镜像（没变的层会走缓存，很快）
docker compose up -d              # 用新镜像重启容器
docker compose ps                 # 全都 healthy 才算成功

# 冒烟：过了才算更新完成
docker compose exec -T backend python /app/scripts/smoke_test.py \
  --base-url http://frontend/api/v1 --health-base http://frontend
```

**怎么判断"要不要重建镜像"**（决定这次更新快不快）：

| 改了什么 | 要不要重建 | 说明 |
| --- | --- | --- |
| 前端源码 / `interpace-frontend/deploy/nginx.conf` | **要重建前端** | 静态产物和 Nginx 配置都烤进镜像里了 |
| 后端 `app/` 代码 / `pyproject.toml` | 要重建后端 | 没改的部分会走层缓存，很快 |
| `config/demo_limits.json` | 要重建后端 | 它是 COPY 进镜像的（想热改就挂载，见上文） |
| `docker-compose*.yml` / `.env` | **不用重建** | compose 文件是运行时读的，`git pull` 后直接 `up -d` 就生效 |
| `docs/` 下的文档 | 不用 | 只是文档 |
| `alembic/versions/` 新增迁移 | 不用手动跑 | 后端容器启动时的 entrypoint 会自动 `alembic upgrade head` |

> 判断方法：`git pull` 之后 `git diff --stat HEAD@{1}` 看一眼改了哪些目录，
> 对照上面这张表即可。全量 `docker compose build` 也不会做无用功——Docker 层缓存会跳过没变的。

回滚到上一个提交：

```bash
git log --oneline -5            # 找到上一个能用的提交
git checkout <那个提交>
docker compose build && docker compose up -d
# 注意："迁移只向前"，回滚代码不代表回滚数据库（见"更新与回滚"一节）
```

### 服务器上构建时的几条经验（2核2G）

1. **加一块 swap 兜底**（vite 构建峰值约 1GB，2G 机器属于紧平衡）：
   ```bash
   fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
   echo '/swapfile none swap sw 0 0' >> /etc/fstab   # 重启后仍生效
   ```
2. **前端依赖走国内镜像**：`NPM_CONFIG_REGISTRY=https://registry.npmmirror.com docker compose build`
   （后端 PyPI 已在 `pyproject.toml` 里配了清华源，不用管）。
3. **首次构建慢是正常的**（下载依赖 + 编译前端），后续改代码再构建会走缓存，快很多。

### 为什么不用 rsync 传源码

一开始文档写的是 `rsync` 把源码推上去。它也能用，但有几个缺点：
服务器上多一份"没有版本信息"的文件（不知道当前跑的是哪个提交）、更新时要手工挑文件、
`.gitignore` 里的规则不会自动生效。**源码走 git** 之后这些都省了，回滚也只是切个提交。

没有 git 可用时（比如仓库是私有的而服务器没有密钥），再用 rsync 或打包：

```bash
# ---- 本机：把源码传上去（排除依赖与产物，通常只有几十 MB）----
rsync -av --delete \
  --exclude 'node_modules' --exclude '.venv' --exclude 'dist' \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '.git' --exclude 'backups' \
  interpace-backend interpace-frontend docker-compose.yml .env \
  root@<服务器>:/opt/interpace/
```

## 服务器构建太慢？用 CI 构建 + 镜像仓库（推荐长期这么做）

在 2核2G 上构建，慢主要慢在三处：**构建镜像要拉基础镜像、装依赖要下几百 MB、
vite 构建还吃满 CPU**。如果不止部署一两次，最省事的是把构建挪到 CI：

### 为什么这么做

- GitHub Actions 的 runner **本来就是 amd64**——不用再纠结跨架构；
- 构建在云端跑，不占服务器的 CPU 和内存；
- 服务器只需要 `docker compose pull`，**从几分钟变成几秒**。

### 三步开启

1. **仓库里已经有工作流**：`.github/workflows/build-images.yml`，打 tag 触发：
   ```bash
   git tag v2026-10-01 && git push origin v2026-10-01
   ```
2. **在 GitHub 仓库的 Settings 里配 4 个值**（Settings → Secrets and variables → Actions）：

   | 类型 | 名字 | 例子 |
   | --- | --- | --- |
   | Variables | `REGISTRY` | `registry.cn-shenzhen.aliyuncs.com` |
   | Variables | `REGISTRY_NAMESPACE` | 你的 ACR 命名空间 |
   | Secrets | `REGISTRY_USERNAME` | ACR 控制台设的固定用户名 |
   | Secrets | `REGISTRY_PASSWORD` | ACR 控制台设的固定密码 |

3. **服务器改成"拉镜像"**：`.env` 里加两行
   ```bash
   IMAGE_PREFIX=registry.cn-shenzhen.aliyuncs.com/你的命名空间/
   IMAGE_TAG=v2026-10-01
   ```
   然后：
   ```bash
   docker compose pull backend frontend
   docker compose up -d
   ./deploy/smoke-test.sh
   ```

### 用 Docker Hub 行不行

行，但**不推荐用在你的场景**：

- 服务器在国内，从 Docker Hub 拉取慢，还常遇到速率限制；
- Docker Hub 免费版的私有仓库数量有限，而阿里云 ACR / 腾讯云 TCR 都有免费额度、国内拉取快。

一定要用的话：`REGISTRY=docker.io`、`REGISTRY_NAMESPACE=你的用户名`，
`IMAGE_PREFIX=docker.io/你的用户名/`。

### 这套流程还没实测过

我本机没法跑 GitHub Actions，工作流文件只做了**结构校验**（YAML 能解析、步骤齐全），
**没有真正跑过一次推送到仓库**。第一次用的时候留意 Actions 页面的日志，
大概率要调的就是仓库地址和凭据这两处。

## 备选：在 amd64 构建机（或 CI）上构建，再离线传输

如果有一台 amd64 机器或 CI，下面这套仍然可用，好处是**服务器上不需要源码**，
更新时也只要传一个镜像包。**前提是构建机必须是 amd64**（在 arm64 Mac 上照这套做，
就会重现上面那个平台不匹配的报错）。

大陆机房拉 Docker Hub 很慢甚至在墙外，离线传输正好绕开这一点：

```bash
# ---- amd64 构建机 ----
docker compose build                     # 构建前后端两个镜像（构建机是 amd64，产物自然是 amd64）

# ⚠️ 只打包**两个应用镜像**，不要把 mysql / redis / minio 一起打进去——见下面的警告
docker save interpace-backend:local interpace-frontend:local \
  | gzip > interpace-app-images.tar.gz
scp interpace-app-images.tar.gz docker-compose.yml .env root@<服务器>:/opt/interpace/
# .env 不进仓库，只能手工传；到服务器上记得把里面的密码/密钥换成正式值

# ---- 服务器 ----
cd /opt/interpace
gunzip -c interpace-app-images.tar.gz | docker load
# 第三方镜像让服务器自己准备：它上面往往已经有了，或者直接 pull 就是对的架构
docker compose pull mysql redis minio     # 镜像已存在时这一步是空操作
docker compose up -d                     # 注意：不带 --build
docker compose ps
```

只要有一台能联网的开发机，这套流程就绕开了服务器拉镜像的所有问题。

> ⚠️ **踩过的坑：`docker load` 会覆盖同名标签。** 第一版流程把 `mysql:8.0` /
> `redis:7-alpine` / `quay.io/minio/minio:latest` 一起打了个包，结果在服务器上
> `docker load` 之后，**这三张原本是 amd64 的镜像被静默替换成了包里的 arm64 版本**，
> 服务直接起不来，而且旧镜像没有其他标签、事后连悬空镜像都找不回来。
> 所以：**只打包应用镜像**，第三方镜像一律让服务器自己 `pull`（或复用已有的）。

### 这套流程实测过（2026-09-30，**在同一台 arm64 Mac 上**）

按上面一字不差地走了一遍（用另一个目录 + 另一个项目名模拟服务器，避免动到本机环境）：

| 步骤 | 实测结果 |
| --- | --- |
| `docker save ... \| gzip` | 当时打了 5 个镜像 → **562 MB**，M1 Pro 上约 66 秒。<br>**改成只打两个应用镜像后是 279 MB**（约 30 秒），更小也更安全 |
| `docker load` | 18 秒，5 个镜像全部恢复（`Loaded image: ...` 五行） |
| 在**只有 `docker-compose.yml` + `.env` + 镜像包**的目录里 `up -d` | ✅ 成功 |
| 全新库启动 | 后端入口自动跑迁移：baseline → add usage_records |
| 五个容器 | 全部 healthy |
| `./deploy/smoke-test.sh` | **全部通过**（含附件上传 + 读回、SSE 流式） |
| 内存占用（生产模式） | frontend 9M + redis 10M + minio 74M + mysql 152M + backend 189M ≈ **434 MiB** |

> ⚠️ **这次验证有个致命盲区**：我把"模拟服务器"和"构建机"放在了同一台 arm64 Mac 上，
> 于是 arm64 镜像在 arm64 上跑得好好的，**架构不匹配的问题完全没暴露**，
> 到了真的 amd64 服务器上才炸。所以上面这张表只证明了"流程本身通"，
> **不能证明"产物能在 amd64 服务器上跑"**——要证明后者，构建机必须是 amd64。
> 这也是下面第 2 条注意事项的由来。

几个从实测里得到的结论：

1. **服务器上不需要源码目录**。运行时只需要 `docker-compose.yml` + `.env` + 镜像本地存在，
   compose 不会因为缺少 `build` 上下文而报错（`image:` 已存在就跳过构建）。
   所以**千万别在服务器上执行带 `--build` 的命令**，那会去找不存在的源码目录。
   （改成"服务器上构建"之后这条就不适用了，那种情况下源码是必须的。）
2. **镜像标签要和 `.env` 里的 `IMAGE_TAG` 对上**。`docker save` / `load` 保留的是 tag，
   如果本机构建时用了 `IMAGE_TAG=v2026-09-30`，那 `save` 和服务器 `.env` 里都必须是这个值，
   否则 compose 会去找 `interpace-backend:local` 找不到而尝试构建 → 失败。
3. **传输时间是主要成本**。562MB 按大陆机房的常见上行带宽估计要几分钟到十几分钟，
   建议挑低峰期传；后续发版只传变化的镜像会更小（可以只 save 后端或前端）。
4. **构建机与服务端架构必须一致**（见本文档开头那节）。用 `docker image inspect <镜像>
   --format '{{.Architecture}}'` 在传输前自检一次，比到服务器上才发现便宜得多。
5. **只打包应用镜像，不要打包第三方镜像**（理由见上面的警告：`docker load` 会覆盖同名标签，
   把服务器上原本正确架构的镜像静默换掉，而且事后可能连悬空镜像都找不回来）。

## MinIO 镜像的坑（实测）

MinIO 的官方镜像地址这几年一直在变，**没有一个"永远能拉到"的地址**：

- `minio/minio:latest`（Docker Hub）：**有的网络能拉，有的直接报
  `repository does not exist or may require 'docker login'`**
  —— 实测：腾讯云的那台服务器**可以正常拉到**（amd64），
  而开发用的 Apple Silicon 机器上拉不到。所以这条完全取决于你的网络，先试一次最省事
- `quay.io/minio/minio:latest`：官方现在主推，但**匿名拉取会被拒**（`unauthorized`），
  需要先 `docker login quay.io`（免费账号）

所以镜像地址做成了**可配置**的（compose 里是 `image: ${MINIO_IMAGE:-minio/minio:latest}`）。
按这个顺序试，通常第一步就成了：

```bash
# 1) 服务器上有没有现成的？有就直接用它的标签（最省事，也避开所有拉取问题）
docker image ls | grep -i minio

# 2) 没有就试 Docker Hub
docker pull minio/minio:latest

# 3) 还不行就登录 quay 再拉
docker login quay.io && docker pull quay.io/minio/minio:latest

# 4) 确定用哪个之后，写进 .env（不用改 compose 文件）
echo 'MINIO_IMAGE=quay.io/minio/minio:latest' >> .env
```

> 这也是 D25（"2核2G 上继续用 MinIO 还是换本地磁盘"）的一个变量：
> 换本地磁盘要重做存储抽象与历史数据迁移，成本明显更大，
> 所以**结论仍然是先留着 MinIO**——只是取镜像这一步得按上面的顺序挑一个能用的源。
## 端口与网络

**对公网发布端口的只有 frontend，其余服务只在容器网络内可达。**

这不是洁癖：后端一旦能被公网直连，配额与限流依赖的"客户端 IP 从哪来"就不成立了
（nginx 会覆盖写 `X-Real-IP`，直连时没人写）。所以 `docker-compose.yml` 里
backend / mysql / redis / minio 都**刻意不写 `ports`**。

> 例外：`mysql` 发布了一个 **回环**端口（`127.0.0.1:3307`），只是为了让你能连上去查数据
> （见下面"想连数据库查数据"）。绑回环意味着外网连不到，不影响上面这条原则。

对外端口由 `WEB_PORT` 控制（默认 80）。本机验证时用 `WEB_PORT=8080` 避开系统占用。

## 服务器上已有 Nginx Proxy Manager 时（推荐这么接）

很多服务器上本来就跑着 **Nginx Proxy Manager（NPM）**，它占着 80/443。
这时**不要**让我们的前端去抢端口，而是接在 NPM 后面——顺带把域名和 HTTPS 一起解决了
（NPM 自带 Let's Encrypt 申请与自动续期，不用自己配 certbot）。

### 1. 找到 NPM 所在的 docker 网络

```bash
docker ps --format '{{.Names}}' | grep -i proxy        # 找到 NPM 容器名
docker inspect <npm容器名> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}'
```

### 2. 在 `.env` 里加两行

```bash
NPM_NETWORK=<上一步查到的网络名>
WEB_PORT=127.0.0.1:8088      # 只绑本机回环，不对公网暴露（端口仍然留着方便本机 curl 排查）
```

### 3. 用叠加文件启动

```bash
docker compose -f docker-compose.yml -f docker-compose.npm.yml up -d
```

`docker-compose.npm.yml` 只做一件事：把 frontend 容器**也接到 NPM 的那个网络**上，
这样 NPM 里就能直接用容器名寻址，不用猜宿主机的 IP。

### 4. 在 NPM 里新建 Proxy Host

| 字段 | 填什么 |
| --- | --- |
| Domain Names | 你的域名，例如 `interpace.sql668.com`（记得先加 DNS 解析到服务器） |
| Scheme | `http` |
| Forward Hostname | `interpace-frontend`（**容器名**，因为两边在同一个 docker 网络里） |
| Forward Port | `80` |
| Block Common Exploits | 打开 |
| **Websockets Support** | **必须打开**——语音面试走 WebSocket，不开会连不上 |
| SSL | 选 Request a new SSL Certificate（Let's Encrypt），勾上 Force SSL |

### 5. Advanced 里再加两条（**很容易漏，漏了会出怪问题**）

在 Proxy Host 的 **Advanced** 标签里粘贴：

```nginx
# 1) SSE 流式对话必须关掉代理缓冲。
#    不关的话，前端打字机效果会变成"憋很久，然后一次性冒出一大段"。
proxy_buffering off;
proxy_cache off;

# 2) 上传附件的体积上限。NPM 默认只有 1MB，传 PDF/录音会直接 413——
#    注意我们自己的 Nginx 里虽然配了 100m，但请求会先被 NPM 拦下。
client_max_body_size 100m;

# 3) 慢接口的读超时。NPM 默认只有几十秒，而我们这几条是"一次模型调用"级别的慢：
#    生成复盘 / 按录音复盘 / 提交答卷评分 —— 模型慢的时候会超过它，
#    表现是 **504**（而且我们内部 Nginx 配的 300s 排在后面，轮不到生效）。
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

**不要在这里重复配 `Upgrade` / `Connection` 那两个头**——面板上勾了 "Websockets Support"
NPM 会自动加，重复写反而可能覆盖掉它的写法。同样也不要自己配 `X-Forwarded-For`：
让 NPM 用它默认的（会追加真实客户端 IP），再由我们内部的 Nginx 用 realip 还原（见 5.5）。

> **关于 `chishin/nginx-proxy-manager-zh`**：它是 NPM 的中文汉化分支（同一套上游），
> Proxy Host 的字段、Advanced 面板、Websockets 开关**完全一样**，上面这些配置照抄即可。
> 唯一区别是它可能落后上游几个版本，但这里用到的
> `proxy_buffering` / WebSocket / realip 都是很老的特性，不受影响。

### 5.5 客户端 IP 的传递（配额正确性的前提）

接在 NPM 后面时，我们的 nginx 看到的 `$remote_addr` 是 **NPM 容器**的地址，不是用户地址。
而配额是按客户端 IP 算的——不处理的话**所有访客共用一个配额桶**，
第一个人的用量会算到所有人头上（现象：别人还没怎么用就被 429 拦掉）。

`deploy/nginx.conf` 里已经用 realip 模块处理好了：

```nginx
set_real_ip_from 10.0.0.0/8;
set_real_ip_from 172.16.0.0/12;
set_real_ip_from 192.168.0.0/16;
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

它把 `$remote_addr` 换成 X-Forwarded-For 里的真实客户端地址，后面的
`proxy_set_header X-Real-IP $remote_addr` 就写对了。

> **安全说明（实测过）**：`set_real_ip_from` 是**按对端地址**校验的——只有来自这些网段的
> 请求，它带的 `X-Forwarded-For` 才会被采信。所以**从公网直连过来的请求伪造不了 IP**
> （对端不在信任表里 → XFF 被忽略 → `$remote_addr` 就是真实来源）。
>
> 实测方式：把信任表改成只含 `10.0.0.0/8`，然后分别从宿主机（对端 192.168.65.1）和
> 另一个容器（对端 172.27.0.5）带 `X-Forwarded-For: 203.0.113.99` 发请求，
> 两次 `$remote_addr` 都是真实对端 ✅。
>
> 仍然建议配合 NPM 部署时把 `WEB_PORT` **绑回环**（`127.0.0.1:8088`）：
> 不是必须，但少一个对外端口就少一类风险——它真正要防的是"内网里有不受控的设备能连到它"。
>
> 实测验证方法（在服务器上执行，会真实调用一次模型）：
> 带 `X-Forwarded-For: 203.0.113.99` 发一轮对话，然后查 `usage_records` 表，
> `client_ip` 应该就是 `203.0.113.99`；如果记的是 `172.x.x.x`（容器网段），说明没生效。

### 6. 之后每次重新部署

重建 frontend 容器后，它的 IP 可能变化。nginx 类代理会在启动时把上游 IP 缓存住，
所以如果出现 **502**，先试一下重建 NPM：

```bash
docker restart <npm容器名>
```

（NPM 的模板里通常带了 `resolver`，多数情况能自动跟上；这条是备用手段。）

## 数据与备份

数据卷：`mysql-data`、`minio-data`、`backend-logs`。

```bash
# 备份数据库
docker compose exec -T mysql sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" inter-pace' \
  | gzip > backup-$(date +%F).sql.gz

# 恢复
gunzip -c backup-2026-09-30.sql.gz | docker compose exec -T mysql \
  sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" inter-pace'

# 注意：`docker compose down` 不删数据卷；只有 `down -v` 才会删，别手滑
```

**实测过**：`docker compose down` 之后再 `up -d`，登录 token 仍然可用、历史消息仍在。

## 想连数据库查数据

### 方式一：直接在服务器上敲（最省事，不用改任何配置）

```bash
cd /opt/interpace
docker compose exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" inter-pace

# 或者一条命令查完就走：
docker compose exec mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" inter-pace \
  -e "select id, username, create_time from users order by id desc limit 5;"
```

（容器里本来就有 `MYSQL_ROOT_PASSWORD` 这个环境变量，不用手打密码。）

### 方式二：用图形客户端（Navicat / DBeaver / TablePlus）

compose 里 MySQL **只绑在宿主机回环**（`127.0.0.1:3307`），所以**走 SSH 隧道**连——
不用动云服务器防火墙：

```bash
# 在你自己电脑上执行，保持这个窗口开着
ssh -N -L 3307:127.0.0.1:3307 root@<服务器IP>
```

然后客户端这样填：

| 字段 | 值 |
| --- | --- |
| 主机 | `127.0.0.1` |
| 端口 | `3307` |
| 用户名 | `root` |
| 密码 | `.env` 里的 `MYSQL_ROOT_PASSWORD` |
| 数据库 | `inter-pace` |

Navicat 也可以把 SSH 填在它的 **SSH 标签**里（主机 = 服务器 IP、用户 root），
那样不用单独开终端，MySQL 标签照样填 `127.0.0.1:3307`。

### 为什么默认绑回环，而不是 `0.0.0.0`

绑回环时**只有能登录这台服务器的人**连得到，外网扫不到。数据库挂公网是很实际的风险：
扫描器几小时内就会找上来，而 MySQL 是"拿到密码就全库"的服务，多一层 SSH 划算得多。

### 真要改成公网直连（不推荐）

编辑 `docker-compose.yml`，把那行改成：

```yaml
    ports:
      - "0.0.0.0:${MYSQL_HOST_PORT:-3307}:3306"
```

然后**必须在云服务器防火墙里只放行你自己的 IP**（别用 `0.0.0.0/0`），
并确认 `MYSQL_ROOT_PASSWORD` 是强随机值。改完 `docker compose up -d mysql` 生效。

> 宿主端口默认用 **3307** 而不是 3306，是为了避开服务器上可能已经存在的本机 MySQL。
> 端口被占用时换一个：`MYSQL_HOST_PORT=33306 docker compose up -d mysql`。

## 更新与回滚

**源码走 git 时（推荐），更新和回滚都是切提交**，比镜像打标签简单得多：

```bash
# ---- 更新 ----
# 本机
git add -A && git commit -m "..." && git push
# 服务器
cd /opt/interpace && git pull
docker compose build && docker compose up -d
./deploy/smoke-test.sh          # 冒烟过了才算更新成功

# ---- 回滚 ----
git log --oneline -5            # 找到上一个能用的提交
git checkout <那个提交>
docker compose build && docker compose up -d
./deploy/smoke-test.sh
# 想回到最新：git checkout main（或你的分支名）
```

### 用镜像标签回滚（离线传输那套才需要）

如果走的是"amd64 构建机 + 离线传镜像"，镜像用 `IMAGE_TAG` 打标签，**回滚就是换标签**
（下面的命令也实测跑过）：

```bash
# 发版：本机构建带新标签的镜像 → 传到服务器 → 改 .env → up
IMAGE_TAG=v2026-09-30 docker compose build backend frontend
docker save interpace-backend:v2026-09-30 interpace-frontend:v2026-09-30 | gzip | ssh ... 'gunzip | docker load'
ssh ... 'cd /opt/interpace && sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=v2026-09-30/" .env && docker compose up -d'

# 回滚：把 IMAGE_TAG 改回**上一个已知可用的标签**，再 up
ssh ... 'cd /opt/interpace && sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=v2026-09-20/" .env && docker compose up -d'
docker compose ps                  # 确认跑的是回滚后的镜像
./deploy/smoke-test.sh             # 冒烟过了才算回滚成功
```

**回滚的前提**：旧镜像还在服务器上（`docker images` 能看到那个 tag）。所以发版时不要
急着 `docker image prune`，至少留一个上一个版本。

**数据库迁移只向前，不会自动回退**。回滚镜像时 schema 是**新的**，所以：

- 加表 / 加字段这类迁移，旧代码照样能跑（本次实测：回滚后冒烟仍全绿）；
- 删字段 / 改类型的迁移，回滚到旧代码就会出错——这种变更要当成"不可回滚"来对待，
  发布前先备份，必要时手工写一条反向迁移。

## 备份与恢复

```bash
# 备份（默认存 ./backups，保留最近 7 份；可配 BACKUP_DIR / KEEP）
./deploy/backup.sh

# crontab：每天凌晨 3 点
# 0 3 * * * cd /opt/interpace && ./deploy/backup.sh >> /var/log/interpace-backup.log 2>&1

# 恢复演练（恢复到临时库，不碰生产库）
./deploy/restore.sh backups/interpace-20260930-103234.sql.gz interpace_restore_drill
# 核对完删掉：
docker compose exec -T -e MYSQL_PWD=... mysql mysql -uroot -e "DROP DATABASE interpace_restore_drill;"
```

备份脚本会做**完整性校验**（gzip 可解压 + 里面有 `CREATE TABLE`）。只检查"文件非空"是不够的——
导出中途失败同样会留下一个非空的坏文件。

**实测过一次完整演练**：备份 → 恢复到临时库 → 表数量 18 与 `alembic_version` 均与生产库一致，
`users` / `sessions` / `chat_messages` / `usage_records` 的行数逐表比对完全相同 → 删除临时库。
**恢复是破坏性的**，演练务必传第二个参数（目标库），别直接往生产库灌。

## 上线冒烟检查

```bash
./deploy/smoke-test.sh        # 在容器里跑，默认打 http://frontend/api/v1
```

覆盖：探活 → 运行时配置 → 注册登录 → 建会话 → 上传附件**并读回**（验证对象存储）→
流式对话（断言 start/delta/done 三种事件）→ 停止接口幂等 → 消息已落库 →
会话/题库/画像/记忆/笔记/检索等接口可达 → 清理数据。

两个刻意的设计：

- **必须经过 Nginx**（默认基地址是 compose 服务名 `frontend`）。直接打后端端口会绕过反代，
  把 SSE 缓冲、反代配置这类问题全漏掉。
- **不对模型产物做断言**。出题生成没生成卷子、简历能不能导出，取决于模型这一轮吐什么；
  拿它当断言，模型心情不好就会把冒烟判成失败，久而久之没人信这个测试。

**它不是摆设**：第一次跑就抓到一个真实的部署缺陷——compose 里 MinIO 的
`MINIO_ROOT_USER/PASSWORD` 没有映射到后端读的 `MINIO_ACCESS_KEY/SECRET_KEY`，
后端退回默认的 `minioadmin`，附件上传直接 500。本地开发不会暴露这个问题。

## 常见故障

| 现象 | 原因与处理 |
| --- | --- |
| **镜像平台不匹配**（`does not match the detected host platform`），redis/mysql 起不来 | 在 arm64 Mac 上构建的镜像被传到了 amd64 服务器。见本文档开头那节：**重新在服务器上构建**，并重新拉 amd64 的第三方镜像 |
| `MYSQL_ROOT_PASSWORD is missing a value` | 没建 `.env`，或文件不叫 `.env`（compose 只认这个名字） |
| 后端起不来，日志停在 `alembic upgrade head` | 数据库连不上或迁移失败。`set -e` 让容器直接退出是刻意的——带着旧 schema 硬启动会更难查 |
| 所有访客被算成同一个 IP，配额异常 | `TRUST_PROXY_HEADERS` 没打开（compose 里已默认 `true`） |
| 上线后前端报"缺少环境变量 VITE_API_BASE_URL" | 前端镜像构建时没拿到该参数。Dockerfile 里已有默认值 `/api/v1`，若改过路径要同步改 `deploy/nginx.conf` |
| 语音面试连不上 | Nginx 少配了 WebSocket 升级头（`deploy/nginx.conf` 里已配，改配置时别删） |
| 流式回答「卡住不动，最后一次性出来」 | Nginx 开了代理缓冲。SSE 那段 location 必须是 `proxy_buffering off` |
| 更新后端后站点开始 502 | Nginx 只在启动时解析一次上游主机名并缓存 IP。`deploy/nginx.conf` 里已用 `resolver 127.0.0.11` + `proxy_pass http://$upstream_backend:8000`（变量形式）让它在运行时重新解析，最多 10 秒切到新 IP；**不要**把变量改回写死的 `backend`，也不要删 `resolver` |
| `ERR_PNPM_IGNORED_BUILDS` 构建失败 | pnpm 10+ 遇到被忽略的构建脚本会直接报错。前端 Dockerfile 里已锁定 `pnpm@9.1.0` |
| redis 报 `Bad directive` | `--save` 指令要两个参数，必须写成独立的 `--save` + 空串（compose 里已按这个写法） |
| 浏览器控制台报 `Prism is not defined` | prismjs 语言包依赖全局 Prism，而核心挂全局的代码在浏览器里不成立。已在 `src/utils/prism-setup.ts` 显式挂上，并让 prismjs 不参与手动分块。**这类错误只有生产构建才会出现**，`pnpm run build` 成功不代表没问题 |
| 本机 `curl` 正常但 Python 脚本报 502 | Docker Desktop 在 macOS 上的端口转发：走 IPv6（`::1`）会 502，用 `127.0.0.1` 就正常。跟项目无关，别在这上面查代码 |
