<script setup lang="ts">
const sections = [
  { title: '题目与测试集', detail: '维护题面、发布门禁和隐藏测试集版本', to: '/admin/problems' },
  { title: '题单运营', detail: '创建题单、添加题目并调整固定顺序', to: '/admin/collections' },
  { title: '每日一题', detail: '按服务端时区安排挑战日期并检查冲突', to: '/admin/daily-challenges' },
  { title: '内容审核', detail: '处理待审核内容、举报、锁帖和置顶', to: '/admin/moderation' },
  { title: '重判中心', detail: '以不可变测试集快照创建受审计重判任务', to: '/admin/rejudge' },
]
</script>

<template>
  <section class="admin-page admin-entry-page">
    <header>
      <p class="eyebrow">ADMINISTRATION</p>
      <h1>管理控制台</h1>
      <p>所有管理操作均连接真实 FastAPI 接口，后端再次校验管理员权限并记录审计日志。</p>
    </header>
    <div class="admin-entry-grid">
      <RouterLink v-for="section in sections" :key="section.to" :to="section.to" class="admin-entry-card">
        <h2>{{ section.title }}</h2>
        <p>{{ section.detail }}</p>
        <span>进入管理 →</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.admin-entry-page { padding-block: 16px 48px; }
.admin-entry-page header { max-width: 760px; }
.eyebrow { color: var(--accent-color, #409eff); font-weight: 700; letter-spacing: .12em; }
.admin-entry-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 32px; }
.admin-entry-card { padding: 20px; border: 1px solid var(--border-color, #dcdfe6); border-radius: 12px; }
.admin-entry-card h2 { margin-top: 0; font-size: 18px; }
.admin-entry-card p { color: var(--muted); line-height: 1.7; }
.admin-entry-card span { color: var(--accent-deep); font-size: 12px; font-weight: 700; }
</style>
