# CodeArena Judge Service

独立的 Redis Streams ACM 判题 Worker。该服务没有公开 HTTP 端口，负责读取提交与隐藏测试数据、启动隔离容器并通过 PostgreSQL 条件更新持久化结果。`backend-api` 不依赖本目录、不会挂载 Docker socket，也不执行用户代码。

## 支持范围

- Python 3.12：`python -I main.py`
- C++20：`g++ -O2 -pipe -std=c++20`
- Accepted、Wrong Answer、Compile Error、Runtime Error、Time Limit Exceeded、Memory Limit Exceeded、System Error
- Redis Streams consumer group、`XAUTOCLAIM` 故障恢复、submission ID 分布式租约和数据库终态幂等

业务判题结果会 `XACK`；PostgreSQL、Redis、MinIO 或 Docker 暂时不可用时保留 pending message，由 `XAUTOCLAIM` 安全重试。数据库终态是幂等性的最终权威，Redis done key 仅是短期提示。

## 本地启动

从仓库根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up --build -d postgres redis minio minio-init backend-api outbox-publisher judge-service
docker compose ps
docker compose logs -f judge-service
```

首次判题时可以由 Judge 拉取受控镜像；生产环境应预拉取并使用镜像 digest，然后设置 `SANDBOX_PULL_IMAGES=false`。

快速测试在 Python 3.12 Docker test stage 中运行：

```powershell
docker build --target test -t codearena-judge-test judge-service
docker run --rm codearena-judge-test python -m ruff check --no-cache .
docker run --rm codearena-judge-test python -m pytest -p no:cacheprovider -m unit
```

真实攻击测试必须显式启用，并且只应在专用开发机或隔离 CI Runner 上运行：

```powershell
docker run --rm --group-add 0 `
  -e RUN_SANDBOX_TESTS=1 `
  -v /var/run/docker.sock:/var/run/docker.sock `
  codearena-judge-test `
  python -m pytest -p no:cacheprovider -m sandbox
```

## 测试数据约定

隐藏输入输出存入 `MINIO_TEST_DATA_BUCKET`，数据库 `test_cases` 只保存 object key。`checksum` 使用：

```text
sha256(input_bytes + b"\0" + expected_output_bytes)
```

Judge 每次读取后校验 checksum。任何隐藏输入、期望输出或实际输出都不会写入公开 API；case result 仅保存用例 ID、状态、耗时、内存和退出码。

## 安全边界

每个 C++ 编译和每个测试用例都创建独立容器，关键参数固定为：

- `network_mode=none`
- `read_only=true`
- UID/GID `65534:65534`
- `cap_drop=ALL`
- `no-new-privileges=true`
- 默认 Docker seccomp，不使用 `seccomp=unconfined`
- CPU、memory=memory-swap、PID、tmpfs 磁盘、输出文件和墙钟时间硬限制
- 不绑定源码目录或测试数据目录；文件经 Docker exec stdin 写入限额 tmpfs
- 容器完成或超时后执行强制删除

挂载 Docker socket 等价于授予 Judge Worker 很高的宿主权限。生产环境必须把 Judge 放在专用节点，优先使用 rootless Docker/userns-remap 或 socket authorization proxy；业务 API 与 Judge 节点应网络隔离。不得把 Docker socket 挂载到 `backend-api`。
