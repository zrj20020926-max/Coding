import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  changeAccountPassword,
  getMyProfile,
  loginAccount,
  logoutAccount,
  logoutAllAccounts,
  refreshAccount,
  registerAccount,
  updateMyProfile,
} from '@/services/auth'
import { AUTH_TOKEN_KEY } from '@/services/http'
import type {
  ChangePasswordPayload,
  LoginPayload,
  ProfileUpdatePayload,
  RegisterPayload,
  UserProfile,
} from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(AUTH_TOKEN_KEY))
  const user = ref<UserProfile | null>(null)
  const loading = ref(false)
  const initialized = ref(false)
  const isAuthenticated = computed(() => Boolean(token.value))

  function acceptSession(accessToken: string, profile: UserProfile): void {
    localStorage.setItem(AUTH_TOKEN_KEY, accessToken)
    token.value = accessToken
    user.value = profile
    initialized.value = true
  }

  function clearSession(): void {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    token.value = null
    user.value = null
    initialized.value = true
  }

  async function login(payload: LoginPayload): Promise<void> {
    loading.value = true
    try {
      const response = await loginAccount(payload)
      acceptSession(response.access_token, response.user)
    } finally { loading.value = false }
  }

  async function register(payload: RegisterPayload): Promise<void> {
    loading.value = true
    try {
      const response = await registerAccount(payload)
      acceptSession(response.access_token, response.user)
    } finally { loading.value = false }
  }

  async function ensureProfile(): Promise<void> {
    if (initialized.value) return
    try {
      if (!token.value) {
        const response = await refreshAccount()
        acceptSession(response.access_token, response.user)
      } else {
        user.value = await getMyProfile()
      }
    }
    catch { clearSession() }
    finally { initialized.value = true }
  }

  async function updateProfile(payload: ProfileUpdatePayload): Promise<void> {
    user.value = await updateMyProfile(payload)
  }

  async function logout(): Promise<void> {
    try { await logoutAccount() }
    finally { clearSession() }
  }

  async function logoutAll(): Promise<void> {
    try { await logoutAllAccounts() }
    finally { clearSession() }
  }

  async function changePassword(payload: ChangePasswordPayload): Promise<void> {
    await changeAccountPassword(payload)
    clearSession()
  }

  return {
    token,
    user,
    loading,
    initialized,
    isAuthenticated,
    acceptSession,
    clearSession,
    login,
    register,
    logout,
    logoutAll,
    changePassword,
    ensureProfile,
    updateProfile,
  }
})
