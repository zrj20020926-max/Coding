import { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'

import { AUTH_TOKEN_KEY, getApiErrorMessage, handleHttpError } from '@/services/http'

describe('HTTP error handling', () => {
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
})
