# 内容运营 API

所有路径均以 `/api/v1` 为前缀。公开列表和详情只展示已发布题单、公开题目以及审核通过且未删除的讨论内容。分页参数使用 `page`、`page_size`，默认值及最大值以 OpenAPI 为准。

## 题单

- `GET /collections`：公开题单分页列表；登录后包含 `solved_count` 和完成率。
- `GET /collections/{slug}`：题单详情及按 `sequence` 排序的题目分页；已下线题目会被过滤，个人 `solved/attempted/favorited` 状态仍按当前用户隔离。
- `GET /admin/collections`、`GET /admin/collections/{id}`：管理员分页查看包括草稿和下线状态在内的题单与完整顺序。
- `POST /admin/collections`、`PATCH /admin/collections/{id}`：管理员创建或编辑题单。
- `PUT /admin/collections/{id}/problems`：管理员一次提交完整且不重复的题目 ID 数组，事务性重排。
- `POST /admin/collections/{id}/publish`、`POST /admin/collections/{id}/offline`：发布与下线。

题单下线不会删除映射；公开响应会立即隐藏整个题单。题目下线也不会删除题单顺序记录，只从公开详情的总数和当前页中排除。

## 每日一题

- `GET /daily-challenge`：返回 `challenge_date`、`timezone` 和公开题目；当天未配置或题目已下线时返回 404。
- `PUT /admin/daily-challenges/{challenge_date}`：管理员按日期新增或覆盖题目。

业务日期完全由服务端 `CONTENT_TIMEZONE` 决定，不接受浏览器日期作为筛选条件。首页卡片展示接口返回的日期和时区，避免用户设备时区造成跨日不一致。

## 讨论、评论和回复

- `GET|POST /problems/{problem_id}/discussions`：讨论分页列表或发帖。
- `GET /discussions/{id}`：讨论详情，以及由 `comments_page/comments_page_size` 控制的平铺评论页。
- `PATCH|DELETE /discussions/{id}`：作者或管理员编辑、软删除讨论。
- `POST /discussions/{id}/comments`：评论；传 `parent_id` 创建回复。
- `PATCH|DELETE /comments/{id}`：作者或管理员编辑、软删除评论。
- `POST /discussions/{id}/reports`、`POST /comments/{id}/reports`：登录用户举报；同一用户对同一目标重复请求不会重复计数。

评论以 `parent_id` 和 `depth` 返回，不递归内嵌。服务端和数据库共同限制最多三级回复，客户端按 `depth` 缩进展示，因此列表大小始终受分页约束。讨论所属题目下线后，普通用户不能继续发现或访问讨论；管理员仍可审核。作者账号删除后，内容保留，`author` 返回 `null`，前端显示“已注销用户”。

## 审核与管理员操作

- `PATCH /admin/discussions/{id}/moderation`、`PATCH /admin/comments/{id}/moderation`：设置 `approved` 或 `rejected` 并记录原因。
- `PATCH /admin/discussions/{id}/controls`：锁帖/解锁、置顶/取消置顶。
- `GET /admin/content-reports`：按状态分页查询举报。
- `PATCH /admin/content-reports/{id}`：标记 `resolved` 或 `dismissed`。

标题或正文命中 `CONTENT_SENSITIVE_WORDS` 后创建为 `pending`；待审内容仅作者和管理员可见。锁帖后普通用户不能新增或编辑评论。管理员每次审核、控帖和举报处理都会写 `content_moderation_actions`，用于追责和运营复核。

## 内容安全边界

- 后端把 Markdown 作为文本保存，不信任 HTML；前端统一通过 `MarkdownContent` 的 DOMPurify 白名单渲染。
- API 不返回隐藏测试用例、MinIO object key、编译命令或 Docker 镜像。
- 本期不开放点赞接口。未来实现点赞时必须新增用户点赞关系和唯一约束，不能直接递增 `like_count`。
- 关键词匹配只是同步预审，不替代人工审核、外部内容安全服务、申诉、审计留存和滥用限流。
