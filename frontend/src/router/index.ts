import { createRouter, createWebHistory } from 'vue-router'
import type { RouteMeta } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export interface GuardRoute {
  fullPath: string
  meta: RouteMeta
}

export interface AuthGuardState {
  isAuthenticated: boolean
  user?: { is_admin: boolean } | null
  ensureProfile: () => Promise<void>
}

export async function runAuthGuard(to: GuardRoute, auth: AuthGuardState) {
  await auth.ensureProfile()
  if (to.meta['requiresAuth'] && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta['requiresAdmin'] && !auth.user?.is_admin) return { name: 'forbidden' }
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
    { path: '/problems', name: 'problems', component: () => import('@/views/ProblemsView.vue') },
    { path: '/guide', name: 'guide', component: () => import('@/views/GuideView.vue') },
    {
      path: '/guide/javascript-v8',
      name: 'guide-javascript-v8',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'javascript-v8' },
    },
    {
      path: '/guide/nodejs',
      name: 'guide-nodejs',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'nodejs' },
    },
    {
      path: '/guide/input-patterns',
      name: 'guide-input-patterns',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'input-patterns' },
    },
    {
      path: '/guide/output-patterns',
      name: 'guide-output-patterns',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'output-patterns' },
    },
    {
      path: '/guide/common-errors',
      name: 'guide-common-errors',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'common-errors' },
    },
    {
      path: '/guide/performance',
      name: 'guide-performance',
      component: () => import('@/views/GuideView.vue'),
      meta: { guideSection: 'performance' },
    },
    { path: '/handbook', redirect: '/guide' },
    { path: '/collections', name: 'collections', component: () => import('@/views/CollectionsView.vue') },
    {
      path: '/collections/:slug',
      name: 'collection-detail',
      component: () => import('@/views/CollectionDetailView.vue'),
    },
    {
      path: '/problems/:slug',
      name: 'problem-detail',
      component: () => import('@/views/ProblemDetailView.vue'),
    },
    {
      path: '/submissions',
      name: 'submissions',
      component: () => import('@/views/SubmissionHistoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/discussions/:id',
      name: 'discussion-detail',
      component: () => import('@/views/DiscussionDetailView.vue'),
    },
    {
      path: '/favorites',
      name: 'favorites',
      component: () => import('@/views/FavoriteProblemsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/submissions/:id',
      name: 'submission-detail',
      component: () => import('@/views/SubmissionDetailView.vue'),
      meta: { requiresAuth: true },
    },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { guestOnly: true } },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { guestOnly: true } },
    { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { requiresAuth: true } },
    { path: '/forbidden', name: 'forbidden', component: () => import('@/views/ForbiddenView.vue') },
    {
      path: '/admin',
      component: () => import('@/components/admin/AdminLayout.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', name: 'admin', component: () => import('@/views/AdminView.vue') },
        { path: 'problems', name: 'admin-problems', component: () => import('@/views/admin/AdminProblemsView.vue') },
        { path: 'problems/new', name: 'admin-problem-new', component: () => import('@/views/admin/AdminProblemEditView.vue') },
        { path: 'problems/:id', name: 'admin-problem-edit', component: () => import('@/views/admin/AdminProblemEditView.vue') },
        { path: 'collections', name: 'admin-collections', component: () => import('@/views/admin/AdminCollectionsView.vue') },
        { path: 'daily-challenges', name: 'admin-daily-challenges', component: () => import('@/views/admin/AdminDailyChallengesView.vue') },
        { path: 'moderation', name: 'admin-moderation', component: () => import('@/views/admin/AdminModerationView.vue') },
        { path: 'rejudge', name: 'admin-rejudge', component: () => import('@/views/admin/AdminRejudgeView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
  ],
  scrollBehavior: (to, _from, savedPosition) => {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, top: 92, behavior: 'smooth' }
    return { top: 0 }
  },
})

router.beforeEach((to) => runAuthGuard(to, useAuthStore()))

export default router
