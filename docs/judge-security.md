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

JavaScript 语法检查和每个隐藏用例分别使用新容器。源码与输入不通过宿主 bind mount 传递，而是经受控 exec stdin 解包到 tmpfs，避免容器访问宿主工作目录。结果读取发生在容器仍存活时，随后强制删除，后台进程和临时文件不会跨用例保留。

用户侧只开放两个运行模式：

- `javascript-v8` 使用 Node.js 22 Debian 镜像内的受控 `vm` 兼容 runner，不宣称为 d8。runner 只注入 `readline()` 与 `print()`：输入先统一 CRLF/LF，`readline()` 每次返回一行且 EOF 固定为 `undefined`，`print(...args)` 以空格连接参数并换行。注入函数移除宿主函数原型链，VM 禁止字符串代码生成和 WebAssembly，不注入 `require`、`process`、`Buffer`、文件系统、网络 API 或 DOM。
- `nodejs` 使用独立 Node.js 22 Alpine 镜像，可使用 `fs.readFileSync(0, 'utf8')`、`console.log()`、`process.stdout.write()`、`Buffer` 和标准 Node API，但没有浏览器 DOM。容器 `network none` 阻断网络，非 root 与只读 rootfs 阻止读取受限文件和写入允许 tmpfs 之外的位置，PID/cgroup/墙钟限制约束子进程。

两种模式不会互相回退：V8 使用 Node API、或 Node.js 直接使用 `readline()/print()`，均返回不含沙箱路径、镜像和内部命令的受控 Runtime Error。兼容 runner 不是安全边界，外层独立 Docker 沙箱仍承担隔离职责。

## 幂等与重试

1. Redis consumer group 把消息放入 PEL，处理完成前不 XACK。
2. Worker 用 `submission_id` 获取带心跳的 Redis 租约，阻止重复消息并发执行。
3. 崩溃消息超过 idle 阈值后由 `XAUTOCLAIM` 领取。
4. Worker 只从消息读取 `submission_id`，随后从 PostgreSQL 加载不可变的 `test_set_id`、题面版本和资源限制快照；激活新测试集不会改变已排队任务。
5. PostgreSQL 使用 `WHERE status = expected` 条件更新；抢不到终态的旧任务不能写 case results。
6. Redis/MinIO/PostgreSQL/Docker 故障不确认消息；AC/WA/CE/RE/TLE/MLE 和确定的配置 System Error 会确认消息。
7. Redis 锁只是并发优化，PostgreSQL 状态机和条件终态更新才是最终一致性保障。

## 隐藏数据

Judge 只在内存中比较 stdout 与期望输出。数据库不保存隐藏输入、期望输出、实际输出或 stderr 摘录；`submission_case_results.stdout_excerpt` 与 `stderr_excerpt` 固定为 NULL。backend-api 的公开 DTO 不包含测试用例关系、MinIO key、compiler output 或内部 error message。

测试数据对象只能由 Judge 与发布门禁使用。管理员测试集响应也只返回用例序号、分值和验证后大小，不返回 object key 或 checksum；FastAPI 参数错误处理不回显非法请求原文，避免错误响应和日志泄漏私有定位信息。`exact` 按规范化行尾和末尾空白比较，`token` 按 token 比较，`float` 使用测试集固化的绝对/相对容差。

## 生产要求

- Judge 使用专用、可销毁节点，不与 API/数据库同宿主。
- 使用 rootless Docker、user namespace remapping、gVisor/Kata 或等价强化运行时。
- sandbox 镜像锁定 digest、离线扫描并预拉取，禁止运行时拉取任意用户指定镜像。
- Docker socket 使用授权代理；Judge 凭证只允许所需容器操作。
- MinIO 分离源码与测试数据 bucket，并为 Judge 使用只读最小权限凭证。
- 监控 PEL idle、重试次数、沙箱创建失败、OOM/TLE 比例和遗留 sandbox 容器。
