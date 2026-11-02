import type { LoginCredentials, TokenResponse, User } from '../types/auth.types'
import apiClient from './api'

export const authService = {
  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', credentials)
    return response.data
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },

  logout(): void {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_data')
  },
}
