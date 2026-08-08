import axios, { AxiosHeaders } from 'axios'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'

import type { AuthResponse } from '@/types/api'

export const AUTH_TOKEN_KEY = 'codearena.access-token'

export const http = axios.create({
  baseURL: import.meta.env['VITE_API_BASE_URL'] ?? '/api/v1',
  timeout: 12_000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export const refreshHttp = axios.create({
  baseURL: import.meta.env['VITE_API_BASE_URL'] ?? '/api/v1',
  timeout: 12_000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _authRetry?: boolean
}

export interface AuthSessionHandlers {
  onSessionRefreshed?: (response: AuthResponse) => void
  onSessionExpired?: () => void
}

let authSessionHandlers: AuthSessionHandlers = {}
let refreshPromise: Promise<AuthResponse> | null = null

export function configureAuthSessionHandlers(handlers: AuthSessionHandlers): void {
  authSessionHandlers = handlers
}

function acceptRefreshedSession(response: AuthResponse): void {
  localStorage.setItem(AUTH_TOKEN_KEY, response.access_token)
  authSessionHandlers.onSessionRefreshed?.(response)
}

export function invalidateAuthSession(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY)
  authSessionHandlers.onSessionExpired?.()
}

export function requestTokenRefresh(): Promise<AuthResponse> {
  if (refreshPromise) return refreshPromise

  const request = refreshHttp
    .post<AuthResponse>('/auth/refresh')
    .then(({ data }) => {
      acceptRefreshedSession(data)
      return data
    })
    .finally(() => {
      if (refreshPromise === request) refreshPromise = null
    })
  refreshPromise = request
  return request
}

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

function isCredentialRequest(config: InternalAxiosRequestConfig): boolean {
  return ['/auth/login', '/auth/register'].some((path) => config.url?.endsWith(path))
}

export async function handleHttpError(error: unknown): Promise<AxiosResponse> {
  const reason = error instanceof Error ? error : new Error('请求失败')
  if (!axios.isAxiosError(error) || error.response?.status !== 401) {
    return Promise.reject(reason)
  }

  if (!error.config) {
    invalidateAuthSession()
    return Promise.reject(reason)
  }

  const config = error.config as RetryableRequestConfig
  if (isCredentialRequest(config)) return Promise.reject(reason)
  if (config._authRetry) {
    invalidateAuthSession()
    return Promise.reject(reason)
  }

  config._authRetry = true
  try {
    const session = await requestTokenRefresh()
    config.headers = AxiosHeaders.from(config.headers)
    config.headers.set('Authorization', `Bearer ${session.access_token}`)
    return await http.request(config)
  } catch {
    invalidateAuthSession()
    return Promise.reject(reason)
  }
}

http.interceptors.response.use((response) => response, handleHttpError)

export function getApiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (!axios.isAxiosError(error)) return fallback
  const body = error.response?.data as { detail?: { message?: string } } | undefined
  return body?.detail?.message ?? fallback
}
