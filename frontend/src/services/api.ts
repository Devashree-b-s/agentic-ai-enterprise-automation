import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds (allows for agent reasoning)
})

// Request interceptor: attach bearer token if present
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor: handle 401s cleanly
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token on authentication failure
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_data')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login?session_expired=true'
      }
    }
    return Promise.reject(error)
  },
)

export default apiClient
