import { describe, expect, it, vi } from 'vitest'

import router, { loginRedirect, runAuthGuard } from '@/router'
import type { AuthGuardState, GuardRoute } from '@/router'

function authState(isAuthenticated: boolean): AuthGuardState {
  return { isAuthenticated, ensureProfile: vi.fn().mockResolvedValue(undefined) }
}

describe('authentication route guard', () => {
  it('redirects anonymous users from protected routes', async () => {
    const auth = authState(false)
    const route: GuardRoute = { fullPath: '/profile', meta: { requiresAuth: true } }

    await expect(runAuthGuard(route, auth)).resolves.toEqual({
      name: 'login',
      query: { redirect: '/profile' },
    })
    expect(auth.ensureProfile).toHaveBeenCalledOnce()
  })

  it('redirects authenticated users away from guest-only routes', async () => {
    const route: GuardRoute = { fullPath: '/login', meta: { guestOnly: true } }

    await expect(runAuthGuard(route, authState(true))).resolves.toEqual({ name: 'profile' })
  })

  it('allows public routes', async () => {
    const route: GuardRoute = { fullPath: '/', meta: {} }

    await expect(runAuthGuard(route, authState(false))).resolves.toBe(true)
  })

  it('preserves the current location when authentication expires', () => {
    expect(loginRedirect('/profile?tab=security')).toEqual({
      name: 'login',
      query: { redirect: '/profile?tab=security' },
    })
  })

  it('hides the administrator route from normal users', async () => {
    const result = await runAuthGuard(
      { fullPath: '/admin', meta: { requiresAuth: true, requiresAdmin: true } },
      {
        isAuthenticated: true,
        user: { is_admin: false },
        ensureProfile: vi.fn().mockResolvedValue(undefined),
      },
    )
    expect(result).toEqual({ name: 'forbidden' })
  })

  it('registers catalog, slug detail and an independent 404 route', () => {
    expect(router.resolve('/problems').name).toBe('problems')
    expect(router.resolve('/problems/a-plus-b').name).toBe('problem-detail')
    expect(router.resolve('/submissions').name).toBe('submissions')
    expect(router.resolve('/favorites').name).toBe('favorites')
    expect(router.resolve('/collections').name).toBe('collections')
    expect(router.resolve('/collections/interview-top').name).toBe('collection-detail')
    expect(router.resolve('/discussions/12').name).toBe('discussion-detail')
    expect(router.resolve('/submissions/00000000-0000-0000-0000-000000000001').name).toBe('submission-detail')
    expect(router.resolve('/this-route-does-not-exist').name).toBe('not-found')
    expect(router.resolve('/forbidden').name).toBe('forbidden')
    expect(router.resolve('/admin/problems').name).toBe('admin-problems')
    expect(router.resolve('/admin/problems/new').name).toBe('admin-problem-new')
    expect(router.resolve('/admin/problems/12').name).toBe('admin-problem-edit')
    expect(router.resolve('/admin/collections').name).toBe('admin-collections')
    expect(router.resolve('/admin/daily-challenges').name).toBe('admin-daily-challenges')
    expect(router.resolve('/admin/moderation').name).toBe('admin-moderation')
    expect(router.resolve('/admin/rejudge').name).toBe('admin-rejudge')
  })
})
