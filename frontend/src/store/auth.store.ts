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
      if (err && typeof err === 'object' && 'response' in err) {
        const res = (err as { response?: { data?: { detail?: string } } }).response
        if (res?.data?.detail) {
          message = res.data.detail
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
