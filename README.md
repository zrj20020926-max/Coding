# CodeArena · JavaScript ACM 输入输出专项训练平台

面向需要掌握 ACM 笔试输入输出的 JavaScript 开发者，系统训练 stdin 输入解析与 stdout 输出格式。平台重点支持 JavaScript V8 的 `readline()/print()` 模式和 Node.js 的 `fs.readFileSync(0, 'utf8')` 模式，不把复杂算法、竞赛排名或企业高频题作为产品主线。

## 当前范围

- Vue 3、TypeScript 严格模式、Vite、Pinia、Vue Router、Element Plus、Monaco Editor
- FastAPI、PostgreSQL、Redis、MinIO
- 注册、登录、JWT + Redis 会话、注销和个人资料
- 15 分钟 Access Token、HttpOnly Refresh Token 轮换、刷新重放检测和多设备撤销
- Alembic 版本迁移与旧数据库安全接管
- 后端 SQLite 快速测试、真实 PostgreSQL 集成测试
- 前端 Vitest、ESLint、类型检查与生产构建
- GitHub Actions CI
- SQLAlchemy 2.0 async 练习、输入输出分类、标签、语言与用户进度模型
- 公开训练课程分页、搜索、结构层级/分类/标签/个人状态筛选与排序
- 公开题目详情、标签和启用语言接口
- 管理员新增、修改、发布和下线题目
- YAML/JSON 幂等题目种子导入
- Monaco 按路由懒加载，支持 JavaScript V8 / Node.js、高亮、补全、主题、字号、格式化和快捷键
- 草稿按用户、题目、语言隔离保存；公开样例与正式提交都通过 MinIO、Outbox、Redis Streams 进入独立 Judge
- 断网/切页恢复、三分钟轮询超时、幂等防重、终态自动停止，以及个人提交历史和安全详情
- 正式判题终态事务性更新进度与统计，支持收藏列表、难度/标签统计和幂等统计重建
- 公开题单、用户完成进度、管理员排序/发布/下线，以及按服务端时区生成的每日一题
- 分页讨论与最多三级回复，支持编辑、软删除、锁帖、置顶、举报、敏感词待审和管理员审计
- Playwright 关键浏览器流程测试

独立 `ai-service` 已提供用户主动触发的失败提交建议分析；浏览器和 `backend-api` 都不会执行用户代码，AI 也不参与正式判题决策。

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
├─ ai-service/                         # 隔离的建议型 AI 分析 Worker
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
- AI metrics：http://localhost:9102/metrics（仅本地 Compose 暴露时）

Docker Compose 会在 API 启动前执行安全迁移入口。全新数据库执行 `upgrade head`；旧版 SQL 创建的数据库只有在结构、扩展、ENUM、索引、触发器和种子数据全部通过校验后才会 stamp。

认证接口还包括 `POST /api/v1/auth/refresh`、`POST /api/v1/auth/change-password` 和
`POST /api/v1/auth/logout-all`。Refresh Token 仅通过 HttpOnly Cookie 传输，不进入响应 JSON；
登录和注册同时按客户端 IP 与规范化账号执行 Redis 限流。

## AI 分析 API

- `POST /api/v1/submissions/{id}/ai-analysis`：当前用户主动分析本人已结束的失败提交。
- `GET /api/v1/submissions/{id}/ai-analysis`：查询结构化分析结果。

AI 与 Judge 使用独立 Redis Stream；AI 只给出错误原因、复杂度、改进建议和引导问题，不修改判题状态。模型输入不含隐藏用例、标准答案、对象键、凭证或其他用户数据，前端固定提示建议可能不准确。配额、缓存、成本、脱敏与部署边界见 [AI 分析文档](docs/ai-analysis.md)，生产观测、告警、备份、Secret Manager 和 digest 规范见 [生产运维文档](docs/production-operations.md)。

## 训练课程 API

公开接口：

- `GET /api/v1/problems`：支持 `q`、`difficulty`、`category`、`tag`、`status`、`page`、`page_size`、`sort`。
- `GET /api/v1/problems/{id}`：公开练习详情。
- `GET /api/v1/tags`：标签列表。
- `GET /api/v1/languages`：启用语言的公开编辑器元数据。

公开语言元数据包含 `runtime_mode`、输入/输出 API 与 EOF 约定，但不包含运行命令或镜像。两种模式是独立运行契约：

- `javascript-v8`（JavaScript V8）：实际运行于 Node.js 22 Debian 沙箱内的受控 `vm` 兼容启动器，并非 d8，也不会开放完整 Node.js API。全局 `readline()` 每次返回一行，EOF 固定返回 `undefined`；`print(...args)` 将参数转为字符串、以单个空格连接并追加换行。`require`、`process`、`Buffer`、文件系统、网络 API 和 DOM 不可用。
- `nodejs`（Node.js 22）：运行于独立 Alpine 沙箱，使用 `fs.readFileSync(0, 'utf8')` 读取原始 stdin，支持 `console.log()`、`process.stdout.write()`、`Buffer` 和标准 Node.js API；不提供 `readline()`、`print()` 或浏览器 DOM，容器网络仍被禁用。

两种模式使用不同镜像、命令和沙箱文件集合。题目可分别配置 `starter_code_v8` 与 `starter_code_nodejs`；未配置时才使用平台通用模板。Node 通用模板不会无条件调用 `trim()`，避免破坏空行和末尾换行训练。

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

训练一级分类包括单值、单行多值、多行、T 组、EOF、哨兵、数组、字符串、矩阵、混合格式、大数据量、输出格式和综合输入输出。数据库仍保留 `easy/medium/hard` 兼容值，但用户侧统一显示“基础/组合/综合”，仅表示输入输出结构复杂度。

## 导入内容种子

参考 `backend-api/seeds/problems.example.yaml`，从 `backend-api/` 执行：

```powershell
.\.venv\Scripts\python -m app.seed.problems seeds/problems.example.yaml
.\.venv\Scripts\python -m app.seed.problems seeds/problems.json
```

导入以标签和题目的 `slug` 为自然键执行 upsert，并同步题目标签关系；重复执行不会创建重复题目或关系。建议在导入前将种子文件纳入评审，并在生产数据库创建恢复点。

种子导入只能创建/更新 `draft` 或 `private` 题目，不能绕过发布门禁。管理员需通过 `/api/v1/admin/problems/{id}/test-sets` 创建测试集，写入 MinIO 隐藏用例元数据，依次执行 `validate`、`activate`，最后调用题目 `publish`。每题仅允许一个 active 测试集；正式提交在创建时快照测试集、题面版本、时间和内存限制，已排队任务不受后续版本切换影响。

## 内容运营 API

- `GET /api/v1/collections`、`GET /api/v1/collections/{slug}`：公开题单分页列表、按运营顺序分页的公开题目及当前用户进度。
- `GET /api/v1/daily-challenge`：按 `CONTENT_TIMEZONE` 返回服务端当天的公开题目：首页展示同一日期与时区。
- `GET|POST /api/v1/problems/{id}/discussions`、`GET /api/v1/discussions/{id}`：分页讨论与分页评论。
- 作者可以编辑、软删除自己的讨论和评论；登录用户可以幂等举报。管理员可以锁帖、置顶、审核内容和处理举报。
- 敏感词命中内容默认进入 `pending`，仅作者和管理员可见；所有 Markdown 在浏览器渲染前经 DOMPurify 白名单清理。

管理员题单、每日一题与审核接口、状态语义和安全边界见[内容运营 API](docs/content-operations.md)。本期未提供点赞入口；数据库遗留的 `like_count` 不作为可写事实源，后续若启用点赞必须先建立用户点赞关系表。

## 完整内容初始化

正式内容位于 `content/`。全新 PostgreSQL 与 MinIO 启动时，Compose 会按 migration、bucket、content-bootstrap、API/Judge/前端的顺序执行；导入失败会阻止 API 假启动。默认 manifest 包含 18 章、168 道 JavaScript ACM 专项练习：105 道输入训练和 63 道输出格式训练，共 336 个公开样例与 1008 个隐藏用例。每题都有 V8/Node.js 独立参考实现、初始模板、前置关系和预计时长；引用实现与隐藏数据不会进入数据库公开字段、前端资源或公开响应。

```powershell
cd backend-api
.\.venv\Scripts\python -m app.bootstrap.content --manifest ../content/manifest.yaml --validate-only --force
.\.venv\Scripts\python -m app.bootstrap.content --manifest ../content/manifest.yaml --dry-run --force
.\.venv\Scripts\python -m app.bootstrap.content --manifest ../content/manifest.yaml --force
```

内容验证会真实运行 Node.js 与受控 V8 兼容参考实现，并注入常见错误读取和错误输出变体：

```powershell
docker compose -f docker-compose.content-test.yml run --build --rm catalog-validator-test
```

详细格式、单题/单题单导入、生产保护和恢复方式见[内容初始化系统](docs/content-bootstrap.md)。

### 管理员初始化

首次管理员必须通过受控 CLI 创建或提升，密码不会写入源码、Compose、README 或日志：

```powershell
cd backend-api
.\.venv\Scripts\python -m app.bootstrap.admin create
.\.venv\Scripts\python -m app.bootstrap.admin promote --username existing_user
```

非交互环境可传 `--username`、`--email`、`--nickname`、`--password`，或使用
`--secret-file C:\secure\codearena-admin.json` 读取 UTF-8 JSON Secret。Secret 文件字段为
`username`、`email`、`nickname`、`password`，不得提交到仓库。创建与提升操作幂等并写入
`audit_logs`；账号/邮箱冲突和弱密码会明确失败，CLI 输出不会包含密码、Token 或密码哈希。

管理员 API 仍由后端 `get_admin_user` 强制鉴权。管理入口包括题目、测试集、题单、每日一题、
讨论审核、举报和 `/api/v1/admin/audit-logs`。测试集批量上传接受包含 `manifest.json` 的 ZIP，
先完成路径、符号链接、压缩比、大小、UTF-8、序号、分值与 checksum 校验后再原子保存。

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

## 完整训练闭环

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
- [内容运营 API](docs/content-operations.md)
- [内容初始化系统](docs/content-bootstrap.md)
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
alembic upgrade head
alembic current
```

`20260812_0009` 会为历史隐藏用例创建 legacy v1 测试集并回填提交快照；`20260813_0013` 增加训练分类并把用户判题语言切换为 JavaScript V8/Node.js；`20260813_0014` 固化两种独立运行契约和题目级模板；`20260814_0015` 修复 submission/attempt 共用状态触发器。由于迁移进程不读取 MinIO，历史用例大小元数据为 0，重新发布前应创建并验证新测试集版本。

若缓存计数因历史数据、运维修复或事件补偿需要校正，可在暂停/排空 Judge 写入后执行幂等重建。命令会获取与 Judge 终态事务互斥的 PostgreSQL advisory lock，并在单事务中重建进度、事件台账和计数：

```powershell
python -m app.maintenance.rebuild_statistics --apply
```

启动后可用 `docker compose logs -f outbox-publisher` 观察发布进程，并用 `redis-cli XINFO STREAM codearena:judge:submissions` 检查任务流。

## JavaScript ACM Judge Worker

`judge-service/` 是独立 Python 服务，通过 Redis Streams 消费任务，用户提交只开放 `javascript-v8` 和 `nodejs`。V8 模式是 Node.js 22 容器内的受控 V8 兼容 runner（不是 d8），只提供 EOF 为 `undefined` 的 `readline()` 和按空格连接并换行的 `print()`；Node.js 模式使用另一镜像直接执行 CommonJS 源码并提供标准 Node API。选错模式会得到受控 Runtime Error 提示，不会退回另一运行时。语法检查和每个测试用例都运行在独立、无网络、只读根目录、非 root、无 capabilities 且受 CPU/内存/PID/tmpfs/输出/墙钟限制的容器中。

```powershell
docker compose up --build -d minio-init backend-api outbox-publisher judge-service
docker compose logs -f judge-service
```

只有 `judge-service` 挂载 Docker socket。`backend-api` 的 Compose 定义没有该挂载，也不得在后续部署中添加。
