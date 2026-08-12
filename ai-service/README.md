# CodeArena AI Service

独立的建议型 AI 分析 Worker。它消费 `codearena:ai:analyses`，只读取失败终态提交、公开题面和用户源码，且从不更新 `submissions.status`。

安全边界：服务不配置隐藏测试数据桶；Redis 消息只含 `analysis_id`；模型输入由固定白名单 DTO 构造并脱敏；日志不记录源码、Prompt、对象键或密钥。生产环境必须通过 Secret Manager 文件挂载提供模型密钥。

本地检查：

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -m unit
```
