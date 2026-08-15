# 真实 full-stack E2E

这套测试与前端现有的快速 Mock Playwright 流程并存。`frontend/e2e/full-stack/` 禁止使用
`page.route()` 或伪造响应，所有注册、登录、内容查询、提交、轮询和进度查询都访问真实
FastAPI；代码经 MinIO、Outbox 和 Redis Streams 后由真实 Judge Docker 沙箱执行。

## 隔离边界

- Compose project 名必须以 `codearena-full-stack-e2e` 开头，脚本遇到其他前缀会拒绝执行。
- PostgreSQL、Redis 和 MinIO 数据目录使用 tmpfs；测试结束仅对该 project 执行 `down -v`。
- 默认前端端口是 `18080`，可通过 `FULL_STACK_FRONTEND_PORT` 修改。
- Judge 测试容器是唯一挂载 Docker socket 的服务。
- 沙箱同时带有 `codearena.role=untrusted-sandbox` 和
  `codearena.environment=codearena-full-stack-e2e` 标签；清理必须同时匹配两个标签。
- Backend、前端与 AI 服务不挂载 Docker socket，也不执行用户代码。

## 运行

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/full-stack-e2e.ps1
```

指定独立端口或 project 后缀：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/full-stack-e2e.ps1 `
  -Project codearena-full-stack-e2e-local -FrontendPort 18081
```

Playwright 默认使用其固定版本 Chromium。本地 CDN 不可用且机器已安装正式 Chrome 时，可仅在
本地设置 `$env:FULL_STACK_BROWSER_CHANNEL='chrome'`；CI 不设置该变量，仍使用锁定版本浏览器。

Linux/CI：

```bash
FULL_STACK_COMPOSE_PROJECT=codearena-full-stack-e2e \
FULL_STACK_FRONTEND_PORT=18080 \
bash scripts/full-stack-e2e.sh
```

首次运行会构建服务镜像并预拉两种 JavaScript 沙箱镜像。启动链路为：

1. PostgreSQL、Redis、MinIO 空实例通过健康检查。
2. Alembic 升级到 head，MinIO 创建隔离 bucket。
3. content bootstrap 导入课程、练习、隐藏测试数据和测试集版本。
4. Backend、Outbox publisher、Judge 和前端启动。
5. `content-invariants-e2e` 直接检查数据库和公开 API 门禁。
6. Playwright 使用真实浏览器执行端到端用户旅程。

可以单独检查 Compose 展开结果：

```powershell
docker compose -p codearena-full-stack-e2e -f docker-compose.content-test.yml config
```

## 覆盖范围

- 至少 80 道输入练习、40 道输出练习、输入/输出/综合课程和速查手册。
- 所有公开练习均有 active 隐藏测试集和 V8/Node.js 初始模板。
- V8 `readline()/print()` 与 Node.js `fs.readFileSync(0, 'utf8')` 真实 Accepted。
- 多行、T 组、EOF、矩阵、BigInt、大输入及精确 stdout 格式。
- 错误运行时、调试输出和错误空格得到受控失败或 Wrong Answer。
- V8/Node.js 草稿隔离、刷新恢复、短暂断网、Worker 重启和重复 Redis 消息幂等。
- 自定义输入不增加正式进度，Pending/System Error 不伪装为用户失败。
- 普通用户无法读取管理员测试集接口，公开 DTO 不含隐藏字段。
- Judge 单独的 sandbox suite 覆盖网络、敏感文件、死循环、内存、子进程、超量输出、
  临时文件写爆和 Worker 中途终止恢复。

## 失败制品与脱敏

运行脚本的 `finally`/shell trap 总会执行
`scripts/collect_full_stack_e2e_artifacts.py`。制品写入
`artifacts/full-stack-e2e/`，其中包括 Compose 状态、服务日志、JUnit 和失败 trace。CI 只在失败
时上传该目录，保留 7 天。

`scripts/sanitize_e2e_artifacts.py` 会递归清理文本与 trace ZIP，删除 trace 内图片并替换密码、
Authorization、JWT、Cookie、Token、用户源码、MinIO object key 和 checksum。Playwright 自身也
禁用 trace screenshot、DOM snapshot、source 和视频；失败截图先将页面替换成不含业务数据的
固定摘要。不要绕过这些设置上传原始 Compose 日志或 Playwright 默认制品。

## 故障恢复

若测试进程被强制终止，先确认 project 名，再只清理隔离环境：

```powershell
docker ps -aq `
  --filter "label=codearena.role=untrusted-sandbox" `
  --filter "label=codearena.environment=codearena-full-stack-e2e" |
  ForEach-Object { if ($_){ docker rm -f $_ } }
docker compose -p codearena-full-stack-e2e -f docker-compose.content-test.yml down -v --remove-orphans
```

不得对默认开发 project 执行 `down -v`，也不得按单个宽泛标签清理全部 Judge 沙箱。修复后
重新运行同一脚本即可获得全新的空环境。启动失败时先查看已经脱敏的
`artifacts/full-stack-e2e/compose-services.log`；内容门禁失败会在浏览器测试前终止，避免把
不完整内容误判为应用已经就绪。
