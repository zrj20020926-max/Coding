# Judge Service 安全与故障模型

## 信任边界

`backend-api`、Outbox publisher 和 Judge Worker 是三个进程边界。API 只接收源码并创建 Outbox；publisher 只发布事件；只有 Judge Worker 能访问 Docker Engine。沙箱容器不能访问 PostgreSQL、Redis、MinIO、业务网络或 Docker socket。

```text
backend-api --no docker socket--> PostgreSQL + MinIO source
       |
       v
Outbox publisher --> Redis Stream
                         |
                         v
judge-service --docker socket--> one isolated compile/case container
```

## 容器约束

沙箱使用 `network none`、只读 rootfs、非 root、`cap-drop ALL`、`no-new-privileges` 和 Docker 默认 seccomp。唯一可写空间是限额 tmpfs；`memory-swap` 等于 `memory`，不允许额外 swap；PID 限制约束 fork bomb；输出同时受 shell/Docker file-size ulimit 与读取上限约束；宿主墙钟超时会杀死并删除整个容器。

C++ 编译和每个隐藏用例分别使用新容器。源码与输入不通过宿主 bind mount 传递，而是经受控 exec stdin 解包到 tmpfs，避免容器访问宿主工作目录。结果读取发生在容器仍存活时，随后强制删除，后台进程和临时文件不会跨用例保留。

## 幂等与重试

1. Redis consumer group 把消息放入 PEL，处理完成前不 XACK。
2. Worker 用 `submission_id` 获取带心跳的 Redis 租约，阻止重复消息并发执行。
3. 崩溃消息超过 idle 阈值后由 `XAUTOCLAIM` 领取。
4. PostgreSQL 使用 `WHERE status = expected` 条件更新；抢不到终态的旧任务不能写 case results。
5. Redis/MinIO/PostgreSQL/Docker 故障不确认消息；AC/WA/CE/RE/TLE/MLE 和确定的配置 System Error 会确认消息。
6. Redis 锁只是并发优化，PostgreSQL 状态机和条件终态更新才是最终一致性保障。

## 隐藏数据

Judge 只在内存中比较 stdout 与期望输出。数据库不保存隐藏输入、期望输出、实际输出或 stderr 摘录；`submission_case_results.stdout_excerpt` 与 `stderr_excerpt` 固定为 NULL。backend-api 的公开 DTO 不包含测试用例关系、MinIO key、compiler output 或内部 error message。

## 生产要求

- Judge 使用专用、可销毁节点，不与 API/数据库同宿主。
- 使用 rootless Docker、user namespace remapping、gVisor/Kata 或等价强化运行时。
- sandbox 镜像锁定 digest、离线扫描并预拉取，禁止运行时拉取任意用户指定镜像。
- Docker socket 使用授权代理；Judge 凭证只允许所需容器操作。
- MinIO 分离源码与测试数据 bucket，并为 Judge 使用只读最小权限凭证。
- 监控 PEL idle、重试次数、沙箱创建失败、OOM/TLE 比例和遗留 sandbox 容器。
