# 生产可观测性与运维

## 结构化日志与审计

`ai-service` 输出 JSON 日志，只包含时间、级别、事件、analysis_id、状态、重试次数和延迟；禁止记录源码、Prompt、题面全文、object key、模型响应原文和密钥。日志平台应再次配置字段级脱敏和 30 天保留期。

`audit_logs` 保存用户主动触发、缓存复用、完成和失败操作。metadata 使用白名单，只记录 submission_id、cache_hit、token 总数、成本和安全错误码。审计日志建议在线保留 180 天，再转不可变归档；用户数据删除应同步遵循合规保留策略。

## 指标与告警

AI Worker 的 `:9102/metrics` 暴露：

- `codearena_ai_analyses_total{outcome}`
- `codearena_ai_provider_retries_total`
- `codearena_ai_provider_latency_seconds`
- `codearena_ai_tokens_total{kind}`
- `codearena_ai_cost_microusd_total`
- `codearena_ai_queue_pending` 与 `codearena_ai_queue_lag`

backend-api 的 `/metrics` 另行暴露 `codearena_ai_analysis_requests_total{outcome}`、`codearena_ai_analysis_cache_hits_total` 和 `codearena_ai_analysis_quota_rejections_total{reason}`。生产环境应仅允许监控网段访问两个指标端点。

推荐告警规则：

- 10 分钟失败率超过 10%，持续 10 分钟；
- Provider P95 延迟超过 25 秒，持续 10 分钟；
- Redis AI consumer group pending 超过 100 或最老消息超过 5 分钟；
- 小时成本超过预算阈值的 80%，达到 100% 时自动关闭触发入口；
- Outbox 未发布事件最老年龄超过 2 分钟；
- AI 配额 Redis、PostgreSQL 或 MinIO 连接失败连续 5 分钟。

告警通知不得包含源码或模型请求/响应。

## Secret Manager

生产密钥只能由云 Secret Manager、Vault 或 Kubernetes Secrets CSI 以只读文件注入：

- `AI_PROVIDER_API_KEY_FILE=/run/secrets/codearena/ai-provider-key`
- PostgreSQL、Redis、MinIO 分别使用独立身份和轮换周期；
- `ai-service` 的 MinIO 账号只允许源码 bucket `GetObject`，显式拒绝隐藏测试 bucket；
- Secret 文件由 uid 10001 只读，禁止进入镜像层、Compose 文件、日志、错误响应和 Git；
- 每 90 天轮换，泄漏时立即吊销并检查审计与成本异常。

`APP_ENV=production` 会拒绝没有 `AI_PROVIDER_API_KEY_FILE` 或未启用 MinIO TLS 的配置。

## 镜像 digest、发布与回滚

CI 构建、SBOM 和漏洞扫描后，将镜像推入私有仓库，以 digest 部署：

```yaml
image: registry.example.com/codearena/ai-service@sha256:<reviewed-digest>
```

PostgreSQL、Redis、MinIO、API、Judge、AI 和前端镜像都应固定 digest；生产禁止 `latest` 和运行时拉取未审核镜像。制品签名须在 admission policy 验证。

发布顺序：备份并验证恢复点；运行单实例 migration job 执行 `alembic upgrade 20260811_0008`；发布 backend-api/outbox publisher；灰度 ai-service；验证指标、审计和一条合成分析；最后发布前端。回滚时先关闭 AI 触发入口并回滚应用镜像，保留向后兼容的 0008 表；不要在事故窗口直接 downgrade 删除分析、台账和审计数据。

## 备份与恢复演练

PostgreSQL 每日全量备份、每 15 分钟 WAL/PITR，备份包含 `ai_analyses`、`ai_usage_records`、`audit_logs` 和 Outbox。MinIO 开启版本化，并仅备份用户源码 bucket；隐藏测试数据使用独立加密、账号和恢复流程。Redis Stream/配额属于可重建或可重投状态，不作为唯一事实源。

每季度在隔离环境执行：

1. 从加密备份恢复 PostgreSQL 到新集群并回放 WAL 到指定时间；
2. 恢复源码 bucket，使用校验和抽检；
3. 以停发模型调用的配置启动 API/AI Worker，验证所有权查询和缓存读取；
4. 重置未发布 Outbox 并验证幂等重投，确认已完成分析不会再次计费；
5. 记录 RPO、RTO、校验结果和审批人，完成后销毁演练数据和临时密钥。

备份本身使用独立 KMS key、不可变保留和跨账号复制；恢复账号不能兼作线上服务账号。
