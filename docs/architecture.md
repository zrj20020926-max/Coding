# JavaScript ACM 输入输出专项训练平台架构设计

## 1. 目标与边界

平台以 JavaScript stdin/stdout 专项训练为产品主线，采用前后端分离和可独立扩缩容的服务边界。API 服务只处理身份、训练内容、提交元数据和任务编排，任何用户代码都不能在 API 容器中执行。

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

Failed submission -> AI outbox/stream -> ai-service -> model provider
```

## 2. 服务职责

| 服务 | 职责 | 明确不负责 |
| --- | --- | --- |
| `frontend` | 登录、训练课程、速查手册、题单、每日一题、讨论、ACM 编辑器、提交/结果展示、个人中心 | 保存密钥、执行代码 |
| `backend-api` | JWT 会话、训练内容、内容运营、提交记录、任务入队、权限校验 | 编译或运行用户代码 |
| `judge-service` | 消费提交、拉取对象、启动沙箱、逐用例判题、上报结果 | 用户认证、公开 REST API |
| `ai-service` | 读取 JavaScript 失败上下文、脱敏并生成 stdin/stdout 结构化诊断 | 决定正式判题结果或提供算法答案 |

AI 队列与 Judge 队列使用不同 Redis Stream 和 consumer group。API 事务只创建分析记录与 Outbox 事件，事件 payload 仅有 `analysis_id`；AI Worker 重新验证提交所有权、公开题目、失败终态以及 `javascript-v8`/`nodejs` 运行模式。它只拥有源码 bucket 的读取权限，不配置隐藏测试 bucket，也不挂载 Docker socket。Provider 未受控配置时 API 立即降级，不创建任务或启动前端轮询。

## 3. 核心数据流

1. 客户端把代码提交给 API；API 校验题目、语言和大小限制。
2. 正式提交在事务内快照 `test_set_id`、题面版本、时间和内存限制；API 将源码写入 MinIO，数据库事务内创建 `submissions(Pending)` 和只含稳定 ID 的 Outbox，随后可靠发布到 Redis Stream。
3. Judge Worker 使用 consumer group 消费任务，以 submission id 做幂等键并把状态改为 `Compiling` / `Running`。
4. Worker 从 PostgreSQL 重新加载 Submission 快照，严格按 `submission.test_set_id` 从 MinIO 读取隐藏数据；每次运行创建独立 Docker 容器。
5. 沙箱禁网、只读根文件系统、非 root 用户运行，并限制 CPU、内存、进程数、输出大小和墙钟时间。
6. Worker 标准化行尾与末尾空白后比较输出，在同一 PostgreSQL 事务中写入终态、用例聚合、统计事件台账、用户进度和计数。
7. 客户端轮询安全状态接口，终态后再读取安全详情；断网、页面隐藏或重开时从本地活动提交恢复。后续可切换 SSE/WebSocket，不改变判题协议。

公开样例与正式提交共享上述控制平面和沙箱。样例模式从题面读取公开输入输出并允许返回该次 stdout，但不写隐藏用例结果、不更新用户正式进度与题目统计；正式模式只从 MinIO 读取隐藏用例，前端只能看到聚合计数。

用户语言只有两种，并且不是同一命令的别名：`javascript-v8` 使用 Node.js 22 Debian 镜像中的受控 `vm` 兼容 runner（不是 d8），仅注入逐行 `readline()` 与 `print()`，EOF 固定为 `undefined`；`nodejs` 使用独立 Alpine 镜像直接运行 Node.js 22 CommonJS，支持 `fs`、`Buffer`、`process.stdout` 等标准 API，但没有 DOM。两者的镜像、启动命令和沙箱文件集合均独立，模式误用不会自动回退。VM context 负责 API 兼容与受控诊断，真正安全边界始终是外层一次性 Docker 沙箱。

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

## 6. 产品信息架构

- 主导航：`首页 / 输入训练 / 输出训练 / 综合练习 / 速查手册 / 我的进度 / 提交记录`。
- 一级分类：单值、单行多值、多行、T 组、EOF、哨兵、数组、字符串、矩阵、混合格式、大数据量、常见输出格式、综合输入输出。
- `easy/medium/hard` 仅作为兼容存储值，界面显示“基础/组合/综合”，描述输入输出结构层级而非算法复杂度。
- 收藏、讨论、认证、题单、每日一题、提交历史和 AI 建议继续复用；排行榜、企业高频和复杂算法能力画像不作为用户侧主入口。

训练内容不再只是一组平铺 Problem，而使用 `Course -> Chapter -> Exercise -> Problem` 组织。Course 定义输入、输出、混合或性能主线，Chapter 定义局部目标和预计时长，Exercise 保存 V8/Node.js 两套指导、初始代码、常见错误以及有向无环前置关系。Problem 继续作为公开题面和判题身份，隐藏测试与参考实现仍留在原有安全边界内。

默认目录按顺序提供 V8 快速入门、Node.js stdin 快速入门、单值和单行、多行、T 组、EOF 与哨兵、数组和矩阵、字符串与空行、混合格式、输出格式、大输入性能和综合训练，共 12 门课程。推荐服务遍历公开有序目录，跳过已完成练习，并只返回所有前置练习已完成的第一项。

当前阶段已实现工程基线、认证、训练目录、提交控制平面、完整前端训练闭环，以及支持 JavaScript V8/Node.js 的 Judge Worker 与 Docker 沙箱执行。

内容运营按“题单 → 每日一题 → 讨论区”分层：题单映射保存稳定顺序，查询时再过滤已下线题目并关联当前用户进度；每日一题以 API 进程配置的 IANA 时区确定业务日期；讨论和评论使用平铺分页与 `parent_id/depth` 表示有限深度回复，避免一次响应递归展开无界评论树。敏感内容先进入待审状态，锁帖/置顶/审核/举报处理均由管理员权限依赖控制，审核动作写入独立审计表。

## 7. 训练统计一致性

正式提交进入终态时，Judge 先以条件更新锁定唯一状态流转，再向 `submission_stat_events` 写入以 `submission_id` 为主键的台账。台账驱动 `user_problem_progress`、用户/题目计数和 `user_exercise_progress` 的确定性聚合；重复终态或重判只更新同一事件，不会新增尝试。进度按 `javascript-v8` 与 `nodejs` 分别统计尝试和首次 Accepted，并派生任一模式完成、双模式完成两个维度。公开样例和 `System Error` 都不进入台账，也不改变课程进度。

统计重建任务获取独占 advisory lock，在线 Judge 终态事务获取共享 lock，避免重建与实时增量相互覆盖。重建以正式终态提交为事实来源，在一个事务内替换进度、台账和派生计数，可安全重复执行。

## 8. 提交控制平面可靠性

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

## 9. 测试集版本与发布门禁

```text
draft -> validating -> ready -> active -> inactive
             `-----> invalid -> validating
```

测试用例只属于明确的 TestSet，不再直接属于 Problem。部分唯一索引保证每题最多一个 active 版本；激活服务先锁题目行，再在同一事务停用旧 active 并激活 ready 版本。被 Submission 引用的测试集和用例不可修改或物理删除，仅允许旧 active 在切换时变为 inactive；只有未引用 draft 可删除。

题目发布不是可见性字段的普通更新。管理员发布时会重新校验 active 测试集的用例数、100 分规则、序号、MinIO 对象存在性/大小/checksum、checker 配置，以及 JavaScript V8/Node.js 可用性；失败返回 `PROBLEM_NOT_READY` 和不含私有定位信息的 issues。创建接口与种子导入均禁止直接写 public，从入口上封堵绕过门禁。
