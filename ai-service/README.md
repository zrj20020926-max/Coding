# CodeArena AI Service

独立的 JavaScript ACM 输入输出诊断 Worker。它消费 `codearena:ai:analyses`，只读取用户本人 `javascript-v8` 或 `nodejs` 的失败终态提交、公开题面和用户源码，且从不更新 `submissions.status`。

结构化结果检查运行模式混用、stdin 读取、行/token/空白/EOF、Number/BigInt、stdout 格式和大输入性能。确定性规则会补强模型诊断，但结果仅为建议，不参与 Judge 状态机。

安全边界：服务不配置隐藏测试数据桶；Redis 消息只含 `analysis_id`；模型输入由固定白名单 DTO 构造并脱敏；日志不记录源码、Prompt、对象键或密钥。模型看不到隐藏测试、标准答案、参考实现、Docker 配置或其他用户数据。生产环境必须通过 Secret Manager 文件挂载提供模型密钥，并在 Provider 就绪后显式设置 backend-api 的 `AI_ANALYSIS_ENABLED=true`。

本地检查：

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -m unit
```
