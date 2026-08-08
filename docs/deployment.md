# 部署说明（当前基线）

## 环境分层

- 本地开发：Vite 5173 + Uvicorn 8000，基础设施由 Docker Compose 启动。
- 集成环境：完整 Docker Compose，Nginx 统一提供 Web 并反向代理 `/api`。
- 生产环境：Web、API、Judge、AI 分别部署；PostgreSQL、Redis、MinIO 使用托管或高可用集群。Judge 节点必须与业务节点分离。

## 配置

从根目录 `.env.example` 创建 `.env`。生产环境必须替换数据库、Redis、MinIO 和 JWT 密钥；JWT 密钥至少 32 个随机字符，不得提交到仓库。`PIP_INDEX_URL` 只影响 API 镜像构建，国内开发默认使用清华镜像，CI 可覆盖为组织内部的可信制品源。

## 启动与检查

```powershell
docker compose config
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health/ready
```

预期健康响应：`{"status":"ready"}`。

## 数据库初始化

`001_schema.sql` 只在全新 PostgreSQL volume 创建时自动执行。当前开发基线使用初始化 SQL；进入持续迭代后切换 Alembic 增量迁移，并把初始化文件收敛成 bootstrap + migrations。

## 上线前强制项

1. 固定所有容器镜像 digest，尤其是 MinIO。
2. JWT/数据库/Redis/MinIO 密钥接入 Secret Manager。
3. 只公开 Web 入口；PostgreSQL、Redis、MinIO API 均进入私网。
4. 为 PostgreSQL 配置自动备份与恢复演练，为 MinIO 配置版本控制和生命周期。
5. Judge 服务上线前完成专用节点、出网阻断、seccomp/AppArmor、只读文件系统、非 root 与资源限制验证。
6. 接入 TLS、结构化日志、指标、告警和审计日志。
