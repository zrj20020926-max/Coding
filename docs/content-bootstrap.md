# 内容初始化系统

## 目录与格式

`content/manifest.yaml` 是唯一入口，所有路径都必须是 manifest 目录内的相对路径，禁止绝对路径和 `..`。Pydantic 模型启用 `extra=forbid`，未知字段、重复 slug/序号/日期、非法时区、分值不等于 100、非法 checker 或越界文件都会在写库前失败。

```text
content/
  manifest.yaml
  tags.yaml
  problems/*.yaml
  test-data/<problem>/*.in|*.out
  reference-solutions/<problem>/solution.py|solution.cpp
  wrong-solutions/*.py
  tools/build_initial_catalog.py
  tools/validate_cpp20.py
  collections.yaml
  daily-challenges.yaml
```

题目文件包含完整题面、数据范围、公开样例与解释、资源限制、标签、发布意图、测试集内容版本、checker、六类隐藏用例元数据以及 Python 3.12/C++20 引用实现路径。引用实现只用于服务端离线验证，不写入数据库、MinIO 和任何公开 DTO。`checksum` 可选；提供时必须等于 `sha256(input + NUL + output)`。Bootstrap 始终重新计算 checksum，对 input/output 分别计算 SHA-256，并生成只保存在数据库内部的内容寻址对象键。

正式初始库含 30 道原创题、180 个隐藏用例、3 个公开题单和从服务端当天起连续 14 天的每日一题。每题六个用例必须分别覆盖最小边界、普通情况、重复元素、特殊结构、性能压力和常见错误反例，分值总和为 100。

## 命令

从 `backend-api/` 执行：

```powershell
python -m app.bootstrap.content --manifest ../content/manifest.yaml --validate-only --force
python -m app.bootstrap.content --manifest ../content/manifest.yaml --dry-run --force
python -m app.bootstrap.content --manifest ../content/manifest.yaml --force
python -m app.bootstrap.content --manifest ../content/manifest.yaml --problem a-plus-b --force
python -m app.bootstrap.content --manifest ../content/manifest.yaml --collection acm-starter --force
```

重新生成固定内容和执行引用实现验证：

```powershell
python ../content/tools/build_initial_catalog.py
docker run --rm -v "${PWD}/../content:/content:ro" -w /content python:3.12-slim `
  python tools/validate_python312.py
docker run --rm -v "${PWD}/../content:/content:ro" -w /content gcc:14.2-bookworm `
  python3 tools/validate_cpp20.py
```

大型用例生成使用固定种子 `20260812`。所有期望输出均由 Python 引用实现生成；验证器用两种语言分别重跑全部隐藏输入并与同一输出文件比较，从而保证结果一致。`wrong-solutions/` 中的 10 份针对性错误实现必须至少在一个隐藏用例上得到 Wrong Answer。

`--validate-only` 只读取并校验本地文件，不连接数据库/MinIO。`--dry-run` 会读取数据库和检查 MinIO 对象，但事务回滚且不上传。`--problem` 只处理单题，不改题单和每日一题；`--collection` 处理该题单及其题目。输出是结构化 JSON，按标签、题目、测试集、用例、对象、题单和每日一题统计 created/updated/skipped/failed；输出和错误不含隐藏数据、对象键、checksum 或底层异常。

## 幂等、版本和事务

- PostgreSQL advisory transaction lock 串行化内容导入。
- 对象键由题目 slug、测试集内容 digest、用例序号和对象 SHA-256 派生；已存在对象会校验后跳过，绝不盲目覆盖。
- active 测试集内容未变化时复用原版本；变化时创建下一数据库版本，完成 MinIO/score/checksum/checker/语言门禁后原子停用旧版本并激活新版本。
- 已被 Submission 引用的旧版本保持 inactive 且不可变，导入器不覆盖或删除。
- 题面变化只增加题面版本，不无故新建测试集；题单映射整组比较并用唯一约束防重；`today` 和 `today+N` 使用 manifest 与服务端一致的 `CONTENT_TIMEZONE` 在导入时解析，不硬编码会过期的日期。
- PostgreSQL 元数据在一个事务中提交。MinIO 或数据库失败会回滚数据库并删除本次新上传对象；内容寻址对象已存在时不计入本次清理。

## Compose 与生产

本地 `docker compose up --build -d` 的依赖链为：

```text
postgres healthy -> db-migrate completed ----+
minio healthy -> minio-init completed -------+-> content-bootstrap completed
                                                   -> backend-api healthy
                                                   -> outbox/judge/ai/frontend
```

`content-bootstrap` 失败时 API 不会启动。`CONTENT_AUTO_IMPORT=false` 会让该 Job 安全输出 disabled 并退出；生产默认应关闭自动导入，通过审核后的独立 Job 使用相同镜像、只读挂载内容目录执行。生产不会自动修改已有标签、已发布题目、active 测试集、公开题单或已有每日一题；受控变更 Job 需要同时设置短期 `CONTENT_ALLOW_PUBLISHED_UPDATES=true` 并显式传入 `--allow-published-updates --force`。内容数据不写入 Alembic migration。

## 故障恢复

失败报告的 `cleanup_failures` 为 0 时数据库已回滚且本次新对象已清理，可修复 manifest、网络或凭据后原命令重试。大于 0 表示 MinIO 删除失败：先根据 Bootstrap 时间窗口和 `content/` 前缀审计对象，仅删除数据库 `test_cases` 未引用的对象，再重试；不得删除 active/inactive 且已被 Submission 引用的版本对象。

若进程在数据库 commit 结果未知时崩溃，先检查题目 active 版本和对象引用，再运行同一 manifest：内容寻址与数据库唯一约束会跳过已完成部分。生产恢复前应备份 PostgreSQL 和版本化 MinIO bucket，并保留旧测试集，禁止通过清卷或直接 SQL 覆盖恢复。
