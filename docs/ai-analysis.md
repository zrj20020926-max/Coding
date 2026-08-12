# AI 代码分析

## 定位与边界

AI 分析是用户主动触发的建议功能，不属于正式判题状态机。`ai-service` 不包含任何更新 `submissions.status` 的 SQL；其失败、超时或停机不会改变 Judge 结果。

仅允许分析当前登录用户本人、公开题目、且状态为 `Wrong Answer`、`Compile Error`、`Runtime Error`、`Time Limit Exceeded` 或 `Memory Limit Exceeded` 的提交。缺失和他人提交统一返回 404；Accepted、System Error 和非终态返回 409。

接口：

- `POST /api/v1/submissions/{submission_id}/ai-analysis`：主动触发或返回已有分析。
- `GET /api/v1/submissions/{submission_id}/ai-analysis`：查询当前用户拥有的分析。

错误保持统一结构：`{"detail":{"code":"...","message":"..."}}`。超出配额返回 `429 AI_QUOTA_EXCEEDED` 和 `Retry-After`；Redis 限额不可用时 fail closed，返回 `503 AI_QUOTA_UNAVAILABLE`，避免失控调用产生费用。

## 数据流与防泄漏

```text
browser -> backend-api -> PostgreSQL(ai_analyses + outbox_events)
                               |
                               v
                       Redis AI Stream -> ai-service -> model provider
```

Outbox 事件只包含 `analysis_id`。Worker 使用白名单查询重新验证所有权、公开题目和失败终态，再从仅有 GetObject 权限的源码桶读取源码。`ai-service` 不配置隐藏测试数据桶。Compose 的只读策略文件以默认 `codearena-submissions` 为资源；如更改 `MINIO_BUCKET`，部署前必须同步生成并审核对应 bucket ARN 的策略。

模型输入白名单只有：

- 公开题面：标题、描述、输入输出说明、公开样例、时间和内存限制；
- 用户本人的源码和语言；
- 脱敏且截断的编译输出；
- 聚合失败摘要：状态、耗时、内存、通过数和总数。

禁止发送或持久化完整 Prompt、隐藏测试输入输出、标准答案、`SubmissionCaseResult`、MinIO object key、凭证、其他用户标识或数据。失败摘要不包含 Judge 原始 `error_message`，避免历史诊断中意外混入隐藏数据。源码、题面和编译输出均按不可信数据包裹；系统提示要求忽略其中的提示词注入。模型响应必须通过 Pydantic JSON Schema 校验。

## 配额、缓存、重试与成本

- 默认每用户每 24 小时 5 次真实模型调用，使用 Redis 原子计数；相同 submission 重复点击直接复用任务。
- 同一用户相同题目版本、源码 checksum 和聚合结果的已完成分析可命中缓存；缓存命中不消耗模型调用配额，但写入使用台账和审计日志。
- 单次模型调用默认 30 秒超时。网络错误、429 和 5xx 最多指数退避重试 3 次；无效结构化输出不重试。
- `ai_usage_records` 按 analysis 幂等记录 provider、model、输入/输出 token、微美元成本和缓存命中。
- 前端固定展示“AI 建议可能不准确，请结合题面、样例和自己的推理判断”。

## 本地运行

在根目录 `.env` 设置本地开发模型 key 后执行：

```powershell
docker compose up --build -d postgres redis minio minio-init backend-api outbox-publisher ai-service frontend
docker compose logs -f ai-service
Invoke-WebRequest http://localhost:9102/metrics
```

生产环境禁止通过普通环境变量注入模型 key，参见 [生产运维](production-operations.md)。
