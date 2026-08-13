import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authService from '@/services/auth'
import { AUTH_TOKEN_KEY } from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/api'

vi.mock('@/services/auth')

const profile: UserProfile = {
  id: '48f6b180-d1bb-4fdd-a3a6-13dc9fb2d22f',
  username: 'candidate_01',
  email: 'candidate@example.com',
  nickname: '候选人一号',
  avatar_url: null,
  bio: null,
  is_admin: false,
  solved_count: 0,
  submission_count: 0,
  accepted_count: 0,
  created_at: '2026-08-08T00:00:00Z',
}

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('persists a successful login session', async () => {
    vi.mocked(authService.loginAccount).mockResolvedValue({
      access_token: 'access-token',
      token_type: 'bearer',
      expires_in: 7200,
      user: profile,
    })
    const store = useAuthStore()

    await store.login({ account: 'candidate_01', password: 'safe-password-123' })

    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(profile)
    expect(store.loading).toBe(false)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('access-token')
  })

  it('clears an invalid persisted session when profile loading fails', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'expired-token')
    vi.mocked(authService.getMyProfile).mockRejectedValue(new Error('unauthorized'))
    const store = useAuthStore()

    await store.ensureProfile()

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(store.initialized).toBe(true)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })

  it('restores a session from the HttpOnly refresh cookie', async () => {
    vi.mocked(authService.refreshAccount).mockResolvedValue({
      access_token: 'restored-access-token',
      token_type: 'bearer',
      expires_in: 900,
      user: profile,
    })
    const store = useAuthStore()

    await store.ensureProfile()

    expect(store.user).toEqual(profile)
    expect(store.token).toBe('restored-access-token')
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('restored-access-token')
  })

  it('always clears local state when logout request fails', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'access-token')
    vi.mocked(authService.logoutAccount).mockRejectedValue(new Error('network error'))
    const store = useAuthStore()

    await expect(store.logout()).rejects.toThrow('network error')
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })

  it('keeps the current session when password validation fails', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'access-token')
    vi.mocked(authService.changeAccountPassword).mockRejectedValue(new Error('wrong password'))
    const store = useAuthStore()
    store.acceptSession('access-token', profile)

    await expect(store.changePassword({
      current_password: 'wrong-password',
      new_password: 'new-safe-password-123',
    })).rejects.toThrow('wrong password')

    expect(store.isAuthenticated).toBe(true)
    expect(store.user).toEqual(profile)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('access-token')
  })

  it('clears every local credential after a successful password change', async () => {
    vi.mocked(authService.changeAccountPassword).mockResolvedValue()
    const store = useAuthStore()
    store.acceptSession('access-token', profile)

    await store.changePassword({
      current_password: 'safe-password-123',
      new_password: 'new-safe-password-123',
    })

    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })
})
