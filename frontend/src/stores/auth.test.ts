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

  it('always clears local state when logout request fails', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'access-token')
    vi.mocked(authService.logoutAccount).mockRejectedValue(new Error('network error'))
    const store = useAuthStore()

    await expect(store.logout()).rejects.toThrow('network error')
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })
})
