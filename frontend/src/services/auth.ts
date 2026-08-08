import type {
  AuthResponse,
  ChangePasswordPayload,
  LoginPayload,
  ProfileUpdatePayload,
  RegisterPayload,
  UserProfile,
} from '@/types/api'
import { http, requestTokenRefresh } from './http'

export async function registerAccount(payload: RegisterPayload): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/register', payload)
  return data
}

export async function loginAccount(payload: LoginPayload): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/login', payload)
  return data
}

export async function logoutAccount(): Promise<void> { await http.post('/auth/logout') }

export async function refreshAccount(): Promise<AuthResponse> {
  return requestTokenRefresh()
}

export async function logoutAllAccounts(): Promise<void> {
  await http.post('/auth/logout-all')
}

export async function changeAccountPassword(payload: ChangePasswordPayload): Promise<void> {
  await http.post('/auth/change-password', payload)
}

export async function getMyProfile(): Promise<UserProfile> {
  const { data } = await http.get<UserProfile>('/users/me')
  return data
}

export async function updateMyProfile(payload: ProfileUpdatePayload): Promise<UserProfile> {
  const { data } = await http.patch<UserProfile>('/users/me', payload)
  return data
}
