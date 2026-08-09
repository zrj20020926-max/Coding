# 训练进度与收藏 API

所有接口使用 `/api/v1` 前缀并要求有效 Access Token。认证失败沿用统一错误结构：

```json
{"detail":{"code":"AUTHENTICATION_REQUIRED","message":"authentication required"}}
```

## 收藏

- `POST /problems/{problem_id}/favorite`：幂等收藏公开题目。
- `DELETE /problems/{problem_id}/favorite`：幂等取消当前用户收藏。
- `GET /favorites?page=1&page_size=20`：按收藏时间倒序返回当前用户的公开题目。

收藏写接口返回 `problem_id` 和 `favorited`。不存在、草稿或下线题目统一返回 `404 PROBLEM_NOT_FOUND`，避免泄露非公开题目。不同用户的收藏由联合主键中的 `user_id` 隔离。

## 题库个人状态

登录用户的题目列表与详情返回 `solved`、`attempted`、`attempt_count`、`favorited`。`GET /problems` 的 `status` 支持：

- `unattempted`：尚无正式终态提交。
- `attempted`：有正式尝试但尚未通过。
- `solved`：至少一次正式 Accepted。
- `favorited`：当前用户已收藏。

这些筛选要求登录；匿名题目响应排除全部个人字段。

## 个人训练面板

`GET /users/me/training` 返回：

- `counters`：已解决题数、正式终态提交数、Accepted 次数。
- `recent_submissions`：当前用户最近 8 条提交的安全摘要。
- `solved_problems`：最近解决的 30 道公开题。
- `difficulty_stats`：按简单、中等、困难统计公开题总数、尝试数和解决数。
- `tag_stats`：按标签统计公开题总数、尝试数和解决数。

响应不包含源码 object key、隐藏测试数据、用例输出摘录、编译命令或 Docker 镜像。

## 计数语义

只有 `mode=judge` 的终态提交计入训练统计；公开样例不计入。每个正式终态以 `submission_stat_events.submission_id` 幂等计数。重复消费同一消息不会重复增加任何计数，同一用户多次通过同一道题也只增加一次 `solved_count`。
