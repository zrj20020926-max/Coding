import { AxiosError, AxiosHeaders } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  AUTH_TOKEN_KEY,
  configureAuthSessionHandlers,
  getApiErrorMessage,
  handleHttpError,
  refreshHttp,
} from '@/services/http'
import { useAuthStore } from '@/stores/auth'
import type { AuthResponse, UserProfile } from '@/types/api'

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

function unauthorizedError(url = '/users/me', adapter = vi.fn()) {
  const config = { url, method: 'get', headers: new AxiosHeaders(), adapter }
  const error = new AxiosError('unauthorized', 'ERR_BAD_REQUEST', config)
  Object.assign(error, {
    response: { status: 401, statusText: 'Unauthorized', data: {}, headers: {}, config },
  })
  return error
}

describe('HTTP error handling', () => {
  beforeEach(() => configureAuthSessionHandlers({}))

  it('returns the structured API message', () => {
    const error = new AxiosError('request failed')
    Object.assign(error, {
      response: {
        status: 409,
        data: { detail: { code: 'ACCOUNT_CONFLICT', message: '用户名已被使用' } },
      },
    })

    expect(getApiErrorMessage(error)).toBe('用户名已被使用')
  })

  it('uses a safe fallback for unknown errors', () => {
    expect(getApiErrorMessage(new Error('internal'), '稍后再试')).toBe('稍后再试')
  })

  it('removes the token after a 401 response and preserves the original error', async () => {
    localStorage.setItem(AUTH_TOKEN_KEY, 'expired-token')
    const error = new AxiosError('unauthorized')
    Object.assign(error, { response: { status: 401, data: {} } })

    await expect(handleHttpError(error)).rejects.toBe(error)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
  })

  it('refreshes once and replays the failed request', async () => {
    const refreshed: AuthResponse = {
      access_token: 'new-access-token',
      token_type: 'bearer',
      expires_in: 900,
      user: profile,
    }
    const onSessionRefreshed = vi.fn()
    configureAuthSessionHandlers({ onSessionRefreshed })
    vi.spyOn(refreshHttp, 'post').mockResolvedValue({ data: refreshed })
    const adapter = vi.fn().mockResolvedValue({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {},
    })

    const response = await handleHttpError(unauthorizedError('/users/me', adapter))

    expect(response.data).toEqual({ ok: true })
    expect(adapter).toHaveBeenCalledOnce()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('new-access-token')
    expect(onSessionRefreshed).toHaveBeenCalledWith(refreshed)
  })

  it('clears both localStorage and Pinia when refresh fails', async () => {
    setActivePinia(createPinia())
    const store = useAuthStore()
    store.acceptSession('expired-token', profile)
    const onSessionExpired = vi.fn(() => store.clearSession())
    configureAuthSessionHandlers({ onSessionExpired })
    vi.spyOn(refreshHttp, 'post').mockRejectedValue(new Error('refresh rejected'))
    const error = unauthorizedError()

    await expect(handleHttpError(error)).rejects.toBe(error)

    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(store.token).toBeNull()
    expect(store.user).toBeNull()
    expect(onSessionExpired).toHaveBeenCalledOnce()
  })
})
