<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()
const themeLabel = computed(() => (ui.theme === 'dark' ? '切换浅色模式' : '切换深色模式'))

async function handleLogout(): Promise<void> {
  await auth.logout()
  await router.push({ name: 'home' })
}
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <RouterLink class="brand" to="/" aria-label="CodeArena 首页">
        <span class="brand-mark" aria-hidden="true">&lt;/&gt;</span><span>CodeArena</span>
      </RouterLink>
      <nav class="site-nav" aria-label="主导航">
        <RouterLink to="/">首页</RouterLink><span class="nav-soon" title="下一迭代开放">题库</span>
      </nav>
      <div class="header-actions">
        <button class="theme-button" type="button" :aria-label="themeLabel" @click="ui.toggleTheme">{{ ui.theme === 'dark' ? '☀' : '◐' }}</button>
        <template v-if="auth.isAuthenticated">
          <RouterLink class="text-link" to="/profile">{{ auth.user?.nickname ?? '个人中心' }}</RouterLink>
          <button class="plain-button" type="button" @click="handleLogout">退出</button>
        </template>
        <template v-else>
          <RouterLink class="text-link" to="/login">登录</RouterLink>
          <RouterLink class="primary-link" to="/register">免费开始</RouterLink>
        </template>
      </div>
    </header>
    <main><RouterView /></main>
  </div>
</template>

