# CodeArena · ACM 模式算法训练平台

面向国内互联网求职程序员的 stdin/stdout 在线算法训练平台。当前完成 **Phase 1 / Sprint 2 题库后端纵切片**：在 Sprint 0 工程基线和认证安全能力上，提供公开题库查询、个人进度筛选、管理员题目生命周期与种子导入。

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

在线编辑器、提交任务、隐藏测试数据管理、Judge Worker 和 AI 分析不属于本次范围。

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
│  └─ src/**/*.test.ts                  # Vitest 测试
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

`status=solved|attempted|unattempted` 需要登录；其中 `attempted` 表示尝试过但尚未通过。登录后的列表和详情会增加 `solved`、`attempted`、`attempt_count`，匿名响应不包含这些字段。普通用户和匿名用户始终只能读取 `visibility=public` 的题目。

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
```

## CI

`.github/workflows/ci.yml` 定义了可复现的后端与前端检查：`pytest`（单元与真实 PostgreSQL 集成测试）、`ruff`、`eslint`、`type-check`、Vitest 和生产构建。

当前远端通过 Gitee 与 GitHub 镜像。GitHub 仓库运行现有 Actions；如使用 Gitee Go，应在其流水线中复用上述命令。

## Git 基线

仓库使用 `.gitignore` 和 `.gitattributes`。`node_modules`、`dist`、`.venv`、测试/工具缓存、覆盖率产物、日志和所有非示例 `.env` 文件均不会进入版本库。

## 文档

- [架构设计](docs/architecture.md)
- [数据模型](docs/database.md)
- [部署与迁移](docs/deployment.md)
