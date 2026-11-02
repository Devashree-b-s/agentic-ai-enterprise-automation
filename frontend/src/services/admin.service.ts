import apiClient from './api'
import type { User, UserRole } from '../types/auth.types'

export interface CreateUserPayload {
  email: string
  password: string
  role: UserRole
  employee_code?: string
}

export const adminService = {
  async createUser(payload: CreateUserPayload): Promise<User> {
    const response = await apiClient.post<User>('/auth/users', payload)
    return response.data
  },
}
