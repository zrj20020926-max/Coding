# 部署与数据库迁移

## 环境分层

- 本地开发：Docker Compose 运行 PostgreSQL、Redis、MinIO、API 与 Web。
- CI：SQLite/FakeRedis 承担快速测试，独立 PostgreSQL 16 服务验证真实 DDL。
- 生产：Web、API、Judge 和 AI 服务独立部署；Judge 节点与业务节点隔离。

## 配置与密钥

从根目录 `.env.example` 创建 `.env`。生产环境必须替换 PostgreSQL、Redis、MinIO 和 JWT 密钥；JWT 密钥至少 32 个随机字符。`.env` 已被 Git 忽略，禁止通过修改忽略规则提交密钥。

`PIP_INDEX_URL` 只影响 API 镜像构建。国内开发默认使用清华镜像；生产 CI 应覆盖为组织内部的可信、可审计制品源。

## 认证安全配置

Access Token 默认有效期为 15 分钟。Refresh Token 使用 HttpOnly Cookie，并在每次刷新后轮换；
服务端只在 Redis 中保存令牌哈希。检测到已轮换令牌重放时，会撤销对应会话族。

生产环境启动前必须满足：

- `JWT_SECRET_KEY` 不是示例值且至少 32 个字符；
- `REFRESH_COOKIE_SECURE=true`；
- `REFRESH_COOKIE_SAMESITE` 为 `lax` 或 `strict`；
- `CORS_ORIGINS` 不包含 `*`；
- `TRUSTED_PROXY_CIDRS` 只配置实际反向代理地址，防止伪造 `X-Forwarded-For` 绕过 IP 限流。

不满足这些条件时，Pydantic Settings 会拒绝创建应用配置，进程直接启动失败。

## Alembic 是唯一结构来源

Sprint 0 起不再挂载 `infra/postgres/init/001_schema.sql`。所有 PostgreSQL 结构变更必须新增 Alembic revision，禁止直接修改已发布的历史迁移。

初始迁移保留：

- `pgcrypto` 与 `citext` 扩展。
- `problem_difficulty`、`problem_visibility`、`submission_status`、`ai_analysis_status` ENUM。
- 题目和提交相关部分索引、唯一部分索引。
- `set_updated_at()` 函数及九个更新时间触发器。
- 五种语言和十个基础标签种子数据。

## 全新数据库

```powershell
cd backend-api
alembic upgrade head
alembic current
```

Docker Compose 会在启动 API 前执行等价的安全迁移入口。

## 接管已有数据库

旧数据卷可能已经由一次性 SQL 创建了全部表，但没有 `alembic_version`。不要直接执行 `alembic stamp head`。

1. 创建数据库快照或可验证备份。
2. 停止所有可能写数据库的 API/Worker。
3. 执行只读检查：

```powershell
cd backend-api
python -m app.db.migration_bootstrap --check-only
```

4. 只有输出状态为 `legacy` 时才执行接管：

```powershell
python -m app.db.migration_bootstrap
alembic current
alembic upgrade head
```

脚本会验证 16 张表、扩展、CITEXT 列、四个 ENUM、十个索引、九个触发器以及种子数据。任一项缺失都会终止，不会写入版本号。

## 生产发布流程

1. 备份并验证恢复点。
2. 在单独的 migration job 中运行 `python -m app.db.migration_bootstrap`。
3. 确认 `alembic current` 等于代码仓库的 head。
4. 如需发布题目，在迁移完成后由单实例任务运行 `python -m app.seed.problems <reviewed-seed.yaml>`。
5. 再滚动发布 API 实例。
6. 检查 `/health/ready`、`/openapi.json`、题库分页接口、错误率和数据库连接指标。

Sprint 2 的迁移 head 为 `20260808_0003`。该版本仅新增公开题目默认排序的部分索引；普通 `CREATE INDEX` 会持有表锁，发布前应在接近生产规模的数据副本上评估耗时并安排维护窗口。旧数据库接管脚本只把已验证的旧结构 stamp 到 `20260808_0001`，随后会依次升级认证版本和题库索引，不会跳过增量迁移。

本地 Compose 将迁移串在 API 启动前，便于开发；生产环境不要让多个 API 副本并发执行迁移。

## 启动与健康检查

```powershell
docker compose config
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health/ready
```

预期响应为 `{"status":"ready"}`。

## 集成测试数据库

`docker-compose.test.yml` 使用独立的 `acm_platform_test` 和 55432 端口，数据目录位于 tmpfs。测试代码还会检查数据库名必须以 `_test` 结尾，以降低误连业务库的风险。

## 上线前遗留安全项

1. 固定容器镜像 digest，尤其是 MinIO。
2. 密钥接入 Secret Manager。
3. PostgreSQL、Redis 和 MinIO 仅开放在私网。
4. 配置自动备份、恢复演练和迁移前快照。
5. Judge 上线前验证专用节点、禁网、seccomp/AppArmor、只读文件系统、非 root 和资源限制。
6. 接入 TLS、结构化日志、指标、告警和审计日志。
