# ACM 算法训练平台架构设计

## 1. 目标与边界

平台采用前后端分离和可独立扩缩容的服务边界。API 服务只处理身份、题库、提交元数据和任务编排，任何用户代码都不能在 API 容器中执行。

```text
Browser / Vue 3
       |
       v
backend-api (FastAPI) ---- PostgreSQL
       |                  Redis session/cache
       |                  MinIO source/test data
       v
Redis Streams: judge.submissions
       |
       v
judge-service workers
       |
       v
Docker sandbox (one container per run, no network, read-only rootfs)
       |
       +---- results stream ----> backend-api / WebSocket or polling

Failed submission ----> ai-service ----> model provider
```

## 2. 服务职责

| 服务 | 职责 | 明确不负责 |
| --- | --- | --- |
| `frontend` | 登录、题库、ACM 编辑器、提交/结果展示、个人中心 | 保存密钥、执行代码 |
| `backend-api` | JWT 会话、题库、提交记录、任务入队、权限校验 | 编译或运行用户代码 |
| `judge-service` | 消费提交、拉取对象、启动沙箱、逐用例判题、上报结果 | 用户认证、公开 REST API |
| `ai-service` | 读取失败上下文、脱敏、生成诊断和复杂度建议 | 决定正式判题结果 |

## 3. 核心数据流

1. 客户端把代码提交给 API；API 校验题目、语言和大小限制。
2. API 将源码写入 MinIO，数据库事务内创建 `submissions(Pending)`，随后使用 outbox/可靠发布把任务写入 Redis Stream。
3. Judge Worker 使用 consumer group 消费任务，以 submission id 做幂等键并把状态改为 `Compiling` / `Running`。
4. Worker 从 MinIO 读取源码与测试数据；每次运行创建独立 Docker 容器。
5. 沙箱禁网、只读根文件系统、非 root 用户运行，并限制 CPU、内存、进程数、输出大小和墙钟时间。
6. Worker 标准化行尾与末尾空白后比较输出，持久化用例结果并发布状态事件。
7. 客户端 MVP 轮询状态；后续可切换 SSE/WebSocket，不改变判题协议。

## 4. 安全基线

- JWT 只存最小声明；`jti` 对应 Redis 登录会话，可主动注销和统一失效。
- 密码使用 Argon2id 单向哈希；登录接口后续增加 IP + 账号双维度限流。
- 测试用例对象私有，客户端永远拿不到隐藏用例的对象 key。
- Judge 主机与业务网段隔离；沙箱使用 `--network none`、`--read-only`、`--cap-drop ALL`、`no-new-privileges`、seccomp/AppArmor。
- Worker 不把 Docker socket 暴露给 API；生产环境优先使用专用判题节点或 sandbox runtime（gVisor/Kata）。
- 所有状态流转使用条件更新，终态不可被过期任务覆盖。

## 5. 状态机

```text
Pending -> Compiling -> Running -> Accepted
                    |          |-> Wrong Answer
                    |          |-> Runtime Error
                    |          |-> Time Limit Exceeded
                    |          `-> Memory Limit Exceeded
                    `-----------> Compile Error
```

`System Error` 用于基础设施故障，并允许按幂等键安全重试；业务判题失败不会自动重试。

## 6. 分阶段交付

- Phase 1：认证、题库、Monaco ACM 编辑器、提交记录、单 Worker 基础判题。
- Phase 2：强化 Docker 沙箱、Redis Streams 可靠消费、MinIO、历史/重提、可观测性。
- Phase 3：AI 分析、排行榜、企业题单、能力与薄弱点分析。

当前阶段已实现工程基线、认证、题库、提交控制平面，以及支持 Python 3.12/C++20 的基础 Judge Worker 与 Docker 沙箱执行。

## 7. 提交控制平面可靠性

```text
POST submission
  -> validate auth / public problem / enabled language / size / rate
  -> put source in MinIO
  -> PostgreSQL transaction [Submission(Pending) + Outbox]
  -> 202 Accepted

outbox-publisher (independent process)
  -> SELECT ... FOR UPDATE SKIP LOCKED
  -> Redis Lua [dedupe event id + XADD stream]
  -> mark Outbox published and persist stream message id
```

API 请求不直接依赖 Redis Streams 是否可用。发布失败时 Outbox 保持未发布状态，记录截断后的错误并指数退避；多个 publisher 使用 `SKIP LOCKED` 分工。Redis Lua 把事件 ID 去重检查、`XADD` 和去重标记放在一次原子执行中，因此数据库提交结果未知后的重试不会产生第二条流消息。事件本身携带稳定 `event_id`，Judge 消费方仍须按该 ID 幂等消费。

MinIO 位于数据库事务之前：写入失败时不创建 Submission；明确的幂等唯一键冲突会删除失败请求刚写入的独立对象。数据库连接中断可能令提交结果未知，此时 API 刻意保留不可变源码，避免“数据库已提交但源码被删除”；生产环境通过生命周期和数据库引用核对清理更安全的孤儿对象失败模式，并为源码 bucket 使用只授予必要前缀权限的独立凭证。
