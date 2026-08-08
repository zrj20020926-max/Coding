export interface UserProfile {
  id: string
  username: string
  email: string
  nickname: string
  avatar_url: string | null
  bio: string | null
  solved_count: number
  submission_count: number
  accepted_count: number
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: UserProfile
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  nickname: string
}

export interface LoginPayload { account: string; password: string }

export interface ProfileUpdatePayload {
  nickname?: string
  avatar_url?: string | null
  bio?: string | null
}

