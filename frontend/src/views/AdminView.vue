<script setup lang="ts">
const sections = [
  { title: '题目与测试集', endpoint: '/api/v1/admin/problems' },
  { title: '题单与每日一题', endpoint: '/api/v1/admin/collections' },
  { title: '讨论举报', endpoint: '/api/v1/admin/content-reports' },
  { title: '审计日志', endpoint: '/api/v1/admin/audit-logs' },
]
</script>

<template>
  <section class="page-container admin-entry-page">
    <header>
      <p class="eyebrow">ADMINISTRATION</p>
      <h1>管理控制台</h1>
      <p>当前版本提供受后端权限保护的管理 API。所有写操作均由服务端再次校验管理员权限并记录审计日志。</p>
    </header>
    <div class="admin-entry-grid">
      <article v-for="section in sections" :key="section.endpoint" class="admin-entry-card">
        <h2>{{ section.title }}</h2>
        <code>{{ section.endpoint }}</code>
      </article>
    </div>
  </section>
</template>

<style scoped>
.admin-entry-page { padding-block: 48px; }
.admin-entry-page header { max-width: 760px; }
.eyebrow { color: var(--accent-color, #409eff); font-weight: 700; letter-spacing: .12em; }
.admin-entry-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 32px; }
.admin-entry-card { padding: 20px; border: 1px solid var(--border-color, #dcdfe6); border-radius: 12px; }
.admin-entry-card h2 { margin-top: 0; font-size: 18px; }
.admin-entry-card code { overflow-wrap: anywhere; }
</style>
