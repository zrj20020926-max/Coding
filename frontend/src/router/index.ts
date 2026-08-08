import { createRouter, createWebHistory } from 'vue-router'
import type { RouteMeta } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export interface GuardRoute {
  fullPath: string
  meta: RouteMeta
}

export interface AuthGuardState {
  isAuthenticated: boolean
  ensureProfile: () => Promise<void>
}

export async function runAuthGuard(to: GuardRoute, auth: AuthGuardState) {
  await auth.ensureProfile()
  if (to.meta['requiresAuth'] && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta['guestOnly'] && auth.isAuthenticated) return { name: 'profile' }
  return true
}

export function loginRedirect(fullPath: string) {
  return { name: 'login', query: fullPath === '/login' ? {} : { redirect: fullPath } }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { guestOnly: true } },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { guestOnly: true } },
    { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => runAuthGuard(to, useAuthStore()))

export default router
