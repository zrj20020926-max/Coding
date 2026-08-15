# JavaScript ACM 输入输出诊断

## 定位与边界

AI 诊断是用户主动触发的建议功能，只帮助定位 JavaScript ACM 模式中的 stdin/stdout 问题。它不提供算法解答，不属于正式判题状态机，也不会执行源码。`ai-service` 没有更新 `submissions.status` 的 SQL；Provider 失败、超时或停机不会改变 Judge 结果。

仅允许分析当前登录用户本人、公开练习、运行时为 `javascript-v8` 或 `nodejs`，且处于下列失败终态的正式提交：

- `Wrong Answer`
- `Compile Error`
- `Runtime Error`
- `Time Limit Exceeded`
- `Memory Limit Exceeded`
- `Output Limit Exceeded`

缺失或他人提交统一返回 404。Accepted、System Error、非终态和非 JavaScript 运行时返回 409。

接口：

- `POST /api/v1/submissions/{submission_id}/ai-analysis`：主动触发或返回已有诊断。
- `GET /api/v1/submissions/{submission_id}/ai-analysis`：查询当前用户拥有的诊断。

错误保持统一结构：`{"detail":{"code":"...","message":"..."}}`。Provider 未配置时立即返回 `503 AI_PROVIDER_NOT_CONFIGURED`，不创建 Pending 记录、不写 Outbox、不消耗配额，前端也不启动轮询。超出配额返回 `429 AI_QUOTA_EXCEEDED` 和 `Retry-After`；Redis 限额不可用时 fail closed，返回 `503 AI_QUOTA_UNAVAILABLE`。

## 数据流与模型输入白名单

```text
browser -> backend-api -> PostgreSQL(ai_analyses + outbox_events)
                               |
                               v
                       Redis AI Stream -> ai-service -> model provider
```

Outbox 事件只包含 `analysis_id`。Worker 使用白名单查询重新验证所有权、公开练习、失败终态和运行模式，再从仅有 GetObject 权限的用户源码桶读取源码。`ai-service` 不配置隐藏测试数据桶，也不挂载 Docker socket。

模型输入仅包含：

- 公开练习：标题、描述、输入格式、输出格式和公开样例；
- 当前运行模式：`javascript-v8` 或 `nodejs`；
- 当前用户自己的源码；
- 脱敏并截断的当前用户编译或运行错误；
- 聚合判题状态、是否为格式不匹配，以及不含测试数据的安全摘要。

模型输入不包含耗时、内存、测试用例数量、`SubmissionCaseResult`、隐藏输入输出、标准答案、参考实现、MinIO object key、凭证、Docker 配置、编译命令、用户标识或其他用户数据。公开题面、源码和错误均作为不可信数据包裹，系统提示明确忽略其中的提示词注入。

## 结构化诊断

模型响应必须通过禁止额外字段的 Pydantic Schema。结果包含九类 `{detected, summary}` 诊断：

- `runtime_mismatch`
- `input_reading_issue`
- `line_parsing_issue`
- `token_parsing_issue`
- `whitespace_issue`
- `eof_issue`
- `numeric_issue`
- `output_format_issue`
- `performance_issue`

另包含 `suggestions`、`guiding_questions` 和 `confidence`。静态规则会补强 V8/Node.js API 混用、无条件 `trim()`、`split(' ')`、CRLF、EOF 越界、Number/BigInt、调试输出、循环内 `shift()`/输出/拼接等常见问题。API 响应仍会执行字段白名单和敏感文本过滤，诊断不得包含隐藏测试、对象位置或内部运行配置。

## 配额、缓存、重试与成本

- 默认每用户每 24 小时 5 次真实模型调用，使用 Redis 原子计数；相同 submission 重复点击直接复用任务。
- 同一用户相同题目版本、运行模式、源码 checksum 和安全聚合结果的已完成诊断可以命中 v2 缓存；旧算法分析缓存不会复用。
- 缓存命中不消耗模型调用配额，但写入使用台账和审计日志。
- 单次调用默认 30 秒超时；网络错误、429 和 5xx 最多指数退避重试 3 次；无效或不安全的结构化输出不重试。
- `ai_usage_records` 按 analysis 幂等记录 provider、model、输入/输出 token、微美元成本和缓存命中。
- 前端轮询最长 90 秒，并固定展示“AI 输入输出诊断可能不准确，仅检查 stdin/stdout 使用方式，不参与正式判题”。

## 配置与本地运行

诊断默认关闭。先以受控方式配置 Provider key，再设置：

```dotenv
AI_ANALYSIS_ENABLED=true
```

本地开发可在根目录 `.env` 设置模型 key；生产环境必须使用 Secret Manager 文件挂载，禁止把 key 写入镜像、Compose、README 或普通日志。启动并查看指标：

```powershell
docker compose up --build -d postgres redis minio minio-init backend-api outbox-publisher ai-service frontend
docker compose logs -f ai-service
Invoke-WebRequest http://localhost:9102/metrics
```

如果 Provider 未配置或需要紧急降级，将 `AI_ANALYSIS_ENABLED=false` 并重启 backend-api。注册、登录、运行、提交和 Judge 均不依赖 AI 服务，仍可正常工作。
