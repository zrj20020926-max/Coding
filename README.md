# CodeArena · ACM 模式算法训练平台

面向国内互联网求职程序员的 stdin/stdout 在线算法训练平台。本仓库按真实商业项目分 Sprint 交付，当前完成 **Phase 1 / Sprint 1：架构基线、核心数据模型与用户认证**。

## 当前能力

- Vue 3 + TypeScript 严格模式 + Vite + Pinia + Vue Router + Element Plus 工程基线
- 响应式首页、注册、登录、个人中心与亮/暗主题
- FastAPI 注册、登录、JWT + Redis 会话、注销、资料查询/修改接口
- Argon2id 密码哈希，Redis 会话支持服务端失效
- PostgreSQL 完整核心 DDL 与语言/标签种子数据
- PostgreSQL、Redis、MinIO、API、Web 的 Docker Compose 基线
- 后端认证集成测试、前端 ESLint/类型检查/生产构建

Monaco 编辑器、题库 API、提交任务和 Judge Worker 将按后续 Sprint 接入；当前安装 Monaco 依赖是为了锁定前端技术基线，不代表判题功能已完成。

## 目录

```text
.
├─ frontend/                    # Vue 3 Web 客户端
├─ backend-api/                 # FastAPI 业务 API
├─ docs/
│  ├─ architecture.md           # 服务边界、判题数据流、安全与状态机
│  ├─ database.md               # ER 模型与数据约束
│  └─ deployment.md             # 本地/部署说明
├─ infra/postgres/init/
│  └─ 001_schema.sql            # PostgreSQL 初始化 DDL + 种子数据
├─ docker-compose.yml
└─ .env.example
```

规划中的独立目录为 `judge-service/` 与 `ai-service/`，在对应 Sprint 开始时创建，避免放置不可运行的空壳服务。

## 快速启动

要求：Docker 29+ 与 Docker Compose 2+。

```bash
cp .env.example .env
docker compose up --build
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
docker compose up --build
```

启动后：

- Web：http://localhost:8080
- OpenAPI：http://localhost:8000/docs
- MinIO Console：http://localhost:9001

首次启动 PostgreSQL 时会自动执行 `infra/postgres/init/001_schema.sql`。如果修改初始化脚本，已有数据卷不会自动重放；开发环境可在确认无需保留数据后执行 `docker compose down -v` 再启动。

## API（当前 Sprint）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册并签发 JWT |
| POST | `/api/v1/auth/login` | 用户名/邮箱登录 |
| POST | `/api/v1/auth/logout` | 注销当前 Redis 会话 |
| GET | `/api/v1/users/me` | 获取当前用户资料 |
| PATCH | `/api/v1/users/me` | 修改昵称、头像和简介 |
| GET | `/health/live` | 进程存活检查 |
| GET | `/health/ready` | PostgreSQL/Redis 就绪检查 |

## 本地测试

后端：

```powershell
cd backend-api
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check .
```

前端：

```powershell
cd frontend
npm install
npm run lint
npm run type-check
npm run build
```

## 下一 Sprint

Phase 1 / Sprint 2 将实现题库纵切片：题目与标签 ORM、管理员种子导入、分页/搜索/难度和标签筛选 API，以及题库列表与题目详情页面。之后再进入 Monaco ACM 编辑器与提交/基础判题，保持每个 Sprint 都可运行、可测试。

