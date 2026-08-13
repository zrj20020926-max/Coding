<script setup lang="ts">
const links = [
  { to: '/admin', label: '概览', exact: true },
  { to: '/admin/problems', label: '题目管理' },
  { to: '/admin/collections', label: '题单运营' },
  { to: '/admin/daily-challenges', label: '每日一题' },
  { to: '/admin/moderation', label: '内容审核' },
  { to: '/admin/rejudge', label: '重判中心' },
]
</script>

<template>
  <div class="admin-shell">
    <aside class="admin-sidebar" aria-label="管理员导航">
      <RouterLink class="admin-sidebar-brand" to="/admin">CodeArena <small>ADMIN</small></RouterLink>
      <nav>
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          :class="{ active: link.exact ? $route.path === link.to : $route.path.startsWith(link.to) }"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
      <RouterLink class="admin-back-link" to="/">返回用户端</RouterLink>
    </aside>
    <section class="admin-main"><RouterView /></section>
  </div>
</template>
