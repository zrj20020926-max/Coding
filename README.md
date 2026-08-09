# CodeArena · ACM 模式算法训练平台

面向国内互联网求职程序员的 stdin/stdout 在线算法训练平台。当前已打通题目详情、ACM 编辑器、可靠提交、独立 Judge 判题、结果轮询、训练进度、收藏和个人统计的完整做题闭环。

## 当前范围

- Vue 3、TypeScript 严格模式、Vite、Pinia、Vue Router、Element Plus、Monaco Editor
- FastAPI、PostgreSQL、Redis、MinIO
- 注册、登录、JWT + Redis 会话、注销和个人资料
- 15 分钟 Access Token、HttpOnly Refresh Token 轮换、刷新重放检测和多设备撤销
- Alembic 版本迁移与旧数据库安全接管
- 后端 SQLite 快速测试、真实 PostgreSQL 集成测试
- 前端 Vitest、ESLint、类型检查与生产构建
- GitHub Actions CI
- SQLAlchemy 2.0 async 题目、标签、语言与用户题目进度模型
- 公开题目分页、搜索、难度/标签/个人状态筛选与排序
- 公开题目详情、标签和启用语言接口
- 管理员新增、修改、发布和下线题目
- YAML/JSON 幂等题目种子导入
- Monaco 按路由懒加载，支持 Python 3.12 / C++20、高亮、补全、主题、字号、格式化和快捷键
- 草稿按用户、题目、语言隔离保存；公开样例与正式提交都通过 MinIO、Outbox、Redis Streams 进入独立 Judge
- 断网/切页恢复、三分钟轮询超时、幂等防重、终态自动停止，以及个人提交历史和安全详情
- 正式判题终态事务性更新进度与统计，支持收藏列表、难度/标签统计和幂等统计重建
- Playwright 关键浏览器流程测试

隐藏测试数据管理后台和 AI 分析仍不属于当前范围；浏览器和 `backend-api` 都不会执行用户代码。

## 目录

```text
.
├─ .github/workflows/ci.yml             # 后端与前端 CI
├─ backend-api/
│  ├─ alembic.ini
│  ├─ migrations/                       # PostgreSQL 版本迁移
│  ├─ seeds/                            # 可审阅的题目种子示例
│  ├─ app/db/migration_bootstrap.py     # 旧库校验、stamp、upgrade
│  ├─ app/models/problem.py             # 题库 async ORM
│  ├─ app/services/problem_import.py    # 幂等种子导入
│  └─ tests/
│     ├─ unit/                          # SQLite + FakeRedis 快速测试
│     └─ integration/                   # 真实 PostgreSQL 测试
├─ frontend/
│  ├─ src/components/editor/            # 懒加载 Monaco 编辑器
│  ├─ src/stores/submissions.ts         # 提交、防重、轮询与恢复
│  ├─ src/**/*.test.ts                  # Vitest 测试
│  └─ e2e/                              # Playwright 关键做题闭环
├─ docs/
├─ docker-compose.yml
└─ docker-compose.test.yml
```

## 快速启动

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

访问地址：

- Web：http://localhost:8080
- OpenAPI：http://localhost:8000/docs
- MinIO Console：http://localhost:9001

Docker Compose 会在 API 启动前执行安全迁移入口。全新数据库执行 `upgrade head`；旧版 SQL 创建的数据库只有在结构、扩展、ENUM、索引、触发器和种子数据全部通过校验后才会 stamp。

认证接口还包括 `POST /api/v1/auth/refresh`、`POST /api/v1/auth/change-password` 和
`POST /api/v1/auth/logout-all`。Refresh Token 仅通过 HttpOnly Cookie 传输，不进入响应 JSON；
登录和注册同时按客户端 IP 与规范化账号执行 Redis 限流。

## 题库 API

公开接口：

- `GET /api/v1/problems`：支持 `q`、`difficulty`、`tag`、`status`、`page`、`page_size`、`sort`。
- `GET /api/v1/problems/{id}`：公开题目详情。
- `GET /api/v1/tags`：标签列表。
- `GET /api/v1/languages`：启用语言的公开编辑器元数据。

`status=solved|attempted|unattempted|favorited` 需要登录；其中 `attempted` 表示尝试过但尚未通过。登录后的列表和详情会增加 `solved`、`attempted`、`attempt_count`、`favorited`，匿名响应不包含这些字段。普通用户和匿名用户始终只能读取 `visibility=public` 的题目。

训练与收藏接口：

- `POST /api/v1/problems/{id}/favorite`、`DELETE /api/v1/problems/{id}/favorite`：幂等收藏/取消收藏公开题目。
- `GET /api/v1/favorites`：当前用户收藏题目分页列表。
- `GET /api/v1/users/me/training`：计数、最近提交、已解决题目、按难度和标签统计。

所有接口只读写当前登录用户的数据；收藏列表不会返回其他用户记录。

管理员接口：

- `POST /api/v1/admin/problems`
- `PATCH /api/v1/admin/problems/{id}`
- `POST /api/v1/admin/problems/{id}/publish`
- `POST /api/v1/admin/problems/{id}/offline`

公开与管理响应均使用显式字段白名单，不包含隐藏测试用例、MinIO object key、编译/运行命令或 Docker 镜像。

## 导入题目种子

参考 `backend-api/seeds/problems.example.yaml`，从 `backend-api/` 执行：

```powershell
.\.venv\Scripts\python -m app.seed.problems seeds/problems.example.yaml
.\.venv\Scripts\python -m app.seed.problems seeds/problems.json
```

导入以标签和题目的 `slug` 为自然键执行 upsert，并同步题目标签关系；重复执行不会创建重复题目或关系。建议在导入前将种子文件纳入评审，并在生产数据库创建恢复点。

## 数据库迁移

以下命令均在 `backend-api/` 目录执行。

全新数据库或已经由 Alembic 管理的数据库：

```powershell
alembic current
alembic upgrade head
```

由旧版 `infra/postgres/init/001_schema.sql` 创建的已有数据库：

```powershell
python -m app.db.migration_bootstrap --check-only
python -m app.db.migration_bootstrap
alembic current
```

安全入口会识别三种状态：

- `empty`：直接执行全部迁移。
- `legacy`：完整验证旧结构，stamp 初始版本后继续 upgrade。
- `versioned`：按 `alembic_version` 正常 upgrade。

只要检测到部分表、缺失 CITEXT/ENUM、索引、触发器或种子数据，脚本就会拒绝 stamp，防止掩盖数据库漂移。

## 测试

### 后端快速测试

```powershell
cd backend-api
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\ruff check .
.\.venv\Scripts\python -m pytest -m unit
```

### 真实 PostgreSQL 集成测试

```powershell
docker compose -f docker-compose.test.yml up -d --wait
$env:TEST_DATABASE_URL='postgresql+asyncpg://acm_test:acm_test_password@localhost:55432/acm_platform_test'
cd backend-api
.\.venv\Scripts\python -m pytest -m integration
cd ..
cd judge-service
..\.tmp\judge-venv\Scripts\python -m pytest -m integration
cd ..
docker compose -f docker-compose.test.yml down
```

集成测试数据库名必须以 `_test` 结尾，否则测试会主动拒绝运行。

### 前端

```powershell
cd frontend
npm ci
npm run lint
npm run type-check
npm run test:run
npm run build
npx playwright install chromium
npm run test:e2e
```

## 完整做题闭环

- `/problems/:slug`：题面与懒加载 ACM 编辑器。`Ctrl/⌘ Enter` 运行公开样例，`Ctrl/⌘ Shift Enter` 正式提交，`Shift Alt F` 格式化。
- `/submissions`：当前用户提交历史；`/submissions/:id`：源码、编译输出、耗时、内存和聚合用例结果。
- `mode=sample` 只读取题面公开样例并可返回该次 stdout，不计入正式刷题进度；`mode=judge` 只读取 MinIO 隐藏数据并更新正式统计。
- API 响应不返回隐藏输入输出、测试数据 object key、源码 object key、编译命令或沙箱镜像。

## CI

`.github/workflows/ci.yml` 定义了可复现的后端与前端检查：`pytest`（单元与真实 PostgreSQL 集成测试）、`ruff`、`eslint`、`type-check`、Vitest、Playwright 和生产构建。

当前远端通过 Gitee 与 GitHub 镜像。GitHub 仓库运行现有 Actions；如使用 Gitee Go，应在其流水线中复用上述命令。

## Git 基线

仓库使用 `.gitignore` 和 `.gitattributes`。`node_modules`、`dist`、`.venv`、测试/工具缓存、覆盖率产物、日志和所有非示例 `.env` 文件均不会进入版本库。

## 文档

- [架构设计](docs/architecture.md)
- [数据模型](docs/database.md)
- [部署与迁移](docs/deployment.md)
- [提交控制平面 API](docs/submissions-api.md)
- [训练进度与收藏 API](docs/training-api.md)
- [Judge 安全与故障模型](docs/judge-security.md)

## 提交控制平面

当前后端已实现提交的可靠接收纵切片，但不执行用户代码：

- `POST /api/v1/submissions` 支持 `Idempotency-Key`、源码大小校验和用户维度 Redis 限频。
- 源码仅写入 MinIO；PostgreSQL 保存 checksum 与内部 object key，公开 DTO 不返回两者。
- `Pending` 提交与 Outbox 事件在同一数据库事务中创建。
- 独立 `outbox-publisher` 服务使用 Redis Lua 原子地去重并写入 Redis Streams；Redis 故障只会延迟发布，不会丢失已接收提交。
- `GET /api/v1/submissions` 与 `GET /api/v1/submissions/{id}` 只返回当前用户的数据，列表支持 `problem_id` 筛选。
- `backend-api` 和 `outbox-publisher` 均不包含用户代码执行路径，不挂载 Docker socket。

迁移至最新结构：

```powershell
cd backend-api
alembic upgrade 20260809_0006
alembic current
```

若缓存计数因历史数据、运维修复或事件补偿需要校正，可在暂停/排空 Judge 写入后执行幂等重建。命令会获取与 Judge 终态事务互斥的 PostgreSQL advisory lock，并在单事务中重建进度、事件台账和计数：

```powershell
python -m app.maintenance.rebuild_statistics --apply
```

启动后可用 `docker compose logs -f outbox-publisher` 观察发布进程，并用 `redis-cli XINFO STREAM codearena:judge:submissions` 检查任务流。

## 基础 ACM Judge Worker

`judge-service/` 是独立 Python 3.12 服务，通过 Redis Streams 消费任务，当前支持 Python 3.12 与 C++20。每次编译和测试用例都运行在独立、无网络、只读根目录、非 root、无 capabilities 且受 CPU/内存/PID/tmpfs/输出/墙钟限制的容器中。

```powershell
docker compose up --build -d minio-init backend-api outbox-publisher judge-service
docker compose logs -f judge-service
```

只有 `judge-service` 挂载 Docker socket。`backend-api` 的 Compose 定义没有该挂载，也不得在后续部署中添加。
