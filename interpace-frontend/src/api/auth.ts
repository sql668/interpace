import api from './http'

export type LoginRequest = {
  username: string
  password: string
}

export type RegisterRequest = {
  username: string
  password: string
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type?: string
  expires_in?: number
}

// 登录
export async function login(payload: LoginRequest) {
  const { data } = await api.post<TokenResponse>('/auth/login', payload)
  return data
}

// 注册
export async function register(payload: RegisterRequest) {
  const { data } = await api.post('/auth/register', payload)
  return data
}
