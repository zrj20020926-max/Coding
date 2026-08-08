import { describe, expect, it, vi } from 'vitest'

import { loginRedirect, runAuthGuard } from '@/router'
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
})
