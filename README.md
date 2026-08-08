# CodeArena · ACM 模式算法训练平台

面向国内互联网求职程序员的 stdin/stdout 在线算法训练平台。当前完成 **Sprint 0 工程基线**：认证业务保持不变，数据库迁移、自动化测试和持续集成已具备可维护基础。

## 当前范围

- Vue 3、TypeScript 严格模式、Vite、Pinia、Vue Router、Element Plus、Monaco Editor
- FastAPI、PostgreSQL、Redis、MinIO
- 注册、登录、JWT + Redis 会话、注销和个人资料
- 15 分钟 Access Token、HttpOnly Refresh Token 轮换、刷新重放检测和多设备撤销
- Alembic 版本迁移与旧数据库安全接管
- 后端 SQLite 快速测试、真实 PostgreSQL 集成测试
- 前端 Vitest、ESLint、类型检查与生产构建
- GitHub Actions CI

题库、在线编辑器、提交任务、Judge Worker 和 AI 分析不属于 Sprint 0，本次没有扩展这些业务。

## 目录

```text
.
├─ .github/workflows/ci.yml             # 后端与前端 CI
├─ backend-api/
│  ├─ alembic.ini
│  ├─ migrations/                       # PostgreSQL 版本迁移
│  ├─ app/db/migration_bootstrap.py     # 旧库校验、stamp、upgrade
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

当前远端托管在 Gitee，GitHub Actions 文件不会由 Gitee 自动执行。启用 Gitee Go 后，应在其流水线中复用上述命令；也可以将仓库镜像到 GitHub 直接运行现有工作流。Sprint 0 不会主动开通远端流水线或推送代码。

## Git 基线

仓库使用 `.gitignore` 和 `.gitattributes`。`node_modules`、`dist`、`.venv`、测试/工具缓存、覆盖率产物、日志和所有非示例 `.env` 文件均不会进入版本库。

## 文档

- [架构设计](docs/architecture.md)
- [数据模型](docs/database.md)
- [部署与迁移](docs/deployment.md)
