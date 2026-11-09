import { create } from 'zustand'
import { authService } from '../services/auth.service'
import type { LoginCredentials, User } from '../types/auth.types'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => void
  initialize: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: true,
  error: null,

  login: async (credentials: LoginCredentials) => {
    set({ isLoading: true, error: null })
    try {
      const data = await authService.login(credentials)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('user_data', JSON.stringify(data.user))
      set({
        token: data.access_token,
        user: data.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      })
    } catch (err: unknown) {
      let message = 'Failed to sign in. Please verify your email and password.'
      if (err && typeof err === 'object') {
        const axiosErr = err as {
          response?: { data?: { detail?: string }; status?: number }
          message?: string
          code?: string
        }
        if (axiosErr.response?.data?.detail) {
          message = axiosErr.response.data.detail
        } else if (
          axiosErr.code === 'ERR_NETWORK' ||
          axiosErr.code === 'ECONNREFUSED' ||
          axiosErr.message?.includes('Network Error')
        ) {
          message =
            'Cannot connect to backend API server. Please ensure the backend is running on http://127.0.0.1:8000.'
        } else if (axiosErr.response?.status === 500) {
          message =
            'Internal server error during authentication. Please check backend logs.'
        }
      }
      set({ error: message, isLoading: false })
      throw new Error(message)
    }
  },

  logout: () => {
    authService.logout()
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      error: null,
    })
  },

  initialize: async () => {
    const token = localStorage.getItem('access_token')
    const cachedUser = localStorage.getItem('user_data')

    if (!token) {
      set({ isLoading: false, isAuthenticated: false, user: null })
      return
    }

    // Populate with cached user initially to reduce flash of unauthenticated state
    if (cachedUser) {
      try {
        const parsed = JSON.parse(cachedUser) as User
        set({ user: parsed, isAuthenticated: true })
      } catch {
        // Ignore JSON parse error
      }
    }

    try {
      const me = await authService.getMe()
      localStorage.setItem('user_data', JSON.stringify(me))
      set({ user: me, isAuthenticated: true, isLoading: false })
    } catch {
      // Token is expired or invalid
      authService.logout()
      set({ user: null, token: null, isAuthenticated: false, isLoading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
