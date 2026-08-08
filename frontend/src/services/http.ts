import axios from 'axios'

export const AUTH_TOKEN_KEY = 'codearena.access-token'

export const http = axios.create({
  baseURL: import.meta.env['VITE_API_BASE_URL'] ?? '/api/v1',
  timeout: 12_000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      localStorage.removeItem(AUTH_TOKEN_KEY)
    }
    const reason = error instanceof Error ? error : new Error('请求失败')
    return Promise.reject(reason)
  },
)

export function getApiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (!axios.isAxiosError(error)) return fallback
  const body = error.response?.data as { detail?: { message?: string } } | undefined
  return body?.detail?.message ?? fallback
}
