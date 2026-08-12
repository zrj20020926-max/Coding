# 提交控制平面 API

本阶段只负责可靠接收、存储、排队和查询。`backend-api` 镜像不包含编译器，也不挂载 Docker socket；它不会编译或执行用户源码。

## 创建提交

`POST /api/v1/submissions`，需要 Bearer Access Token。

```http
Idempotency-Key: editor-click-20260808-0001
Content-Type: application/json

{
  "problem_id": 1,
  "language": "python",
  "source_code": "print(input())",
  "mode": "judge"
}
```

`mode=sample` 表示运行题面公开样例，`mode=judge` 表示正式隐藏用例判题。两种模式都走相同的 MinIO、Outbox、Redis Streams 和独立 Judge 链路；限频与幂等指纹包含模式，样例运行不会阻塞正式提交。

成功返回 `202 Accepted`。`Idempotency-Key` 可选、最长 128 个可打印字符；同一用户使用相同键和相同请求重试时返回原提交，并令 `idempotent_replay=true`。相同键用于不同题目、语言或源码时返回 `409 IDEMPOTENCY_KEY_REUSED`。

服务校验账号状态、公开题目、启用语言、UTF-8 源码字节数和用户提交间隔。正式模式还要求题目存在 active 测试集。源码写入 MinIO 后，API 在一个 PostgreSQL 事务中创建 `Pending` Submission 与 `submission.created` Outbox 事件，并快照 `test_set_id`、题面版本、时间限制和内存限制；事件 payload 只含 `event_id` 与 `submission_id`。MinIO 失败返回 503，且不产生数据库记录。

## 查询

- `GET /api/v1/submissions/{id}/status`：仅返回轮询所需的安全聚合状态，不读取 MinIO 源码。
- `GET /api/v1/submissions/{id}`：仅查询当前用户自己的安全详情；不存在和无权访问统一返回 404。详情可返回用户自己的源码、编译输出和诊断；只有 `sample` 模式可返回该次公开样例 stdout。
- `GET /api/v1/submissions?page=1&page_size=20&problem_id=1`：当前用户提交列表，可按题目 ID 筛选。

列表和状态响应仅包含题目和语言的公开元数据、模式、状态、耗时、内存、用例计数、分数与时间戳。以下内部字段永不进入公开 DTO：MinIO object key、checksum、Outbox/Redis message id、隐藏用例输入输出、编译命令、运行命令和 Docker 镜像。

## 错误码

错误继续使用统一的 `{"detail":{"code":"...","message":"..."}}` 结构。

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | `INVALID_IDEMPOTENCY_KEY` | 幂等键格式不合法 |
| 400 | `LANGUAGE_UNAVAILABLE` | 语言不存在或已停用 |
| 401 | `UNAUTHORIZED` | 登录状态无效 |
| 404 | `PROBLEM_NOT_FOUND` | 题目不存在或不是公开状态 |
| 404 | `SUBMISSION_NOT_FOUND` | 提交不存在或不属于当前用户 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 幂等键绑定了不同请求 |
| 409 | `PROBLEM_NOT_READY` | 正式提交的题目没有 active 隐藏测试集 |
| 413 | `SOURCE_TOO_LARGE` | 源码超过字节上限 |
| 429 | `SUBMISSION_RATE_LIMITED` | 提交过于频繁，响应包含 `Retry-After` |
| 503 | `SOURCE_STORAGE_UNAVAILABLE` | MinIO 暂时不可用 |
| 503 | `RATE_LIMIT_UNAVAILABLE` | Redis 限频暂时不可用，默认 fail closed |

## 状态约束

```text
Pending -> Compiling -> Running -> Accepted
                    |          |-> Wrong Answer
                    |          |-> Runtime Error
                    |          |-> Time Limit Exceeded
                    |          |-> Memory Limit Exceeded
                    |          `-> System Error
                    |-> Compile Error
                    `-> System Error
```

除保持原状态外，其他跳转均被服务层状态机和 PostgreSQL 触发器拒绝；终态不可回退。本阶段没有提供公开的状态更新接口，后续 Judge 结果接收端必须复用该状态机。
