export type UserRole = 'Admin' | 'Manager' | 'HR' | 'Employee'

export interface User {
  id: number
  email: string
  role: UserRole
  is_active: boolean
  employee_id: number | null
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface LoginCredentials {
  email: string
  password: string
}
