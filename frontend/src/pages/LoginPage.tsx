import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Building2, Lock, Mail, AlertCircle, ArrowRight, Shield } from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Button from '../components/common/Button'

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const { login, isLoading, isAuthenticated } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  // Redirect if already authenticated
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError(null)

    if (!email.trim() || !password) {
      setLocalError('Please enter both email and password.')
      return
    }

    try {
      await login({ email: email.trim(), password })
      navigate(from, { replace: true })
    } catch (err: unknown) {
      if (err instanceof Error) {
        setLocalError(err.message)
      } else {
        setLocalError('Authentication failed. Please verify credentials.')
      }
    }
  }

  // Helper demo accounts for fast pairing and review
  const demoAccounts = [
    { label: 'Admin', email: 'admin@enterprise.com', role: 'System Admin' },
    { label: 'Manager', email: 'manager@enterprise.com', role: 'Sales & Inventory' },
    { label: 'HR User', email: 'hr@enterprise.com', role: 'Staffing & Leaves' },
    { label: 'Employee', email: 'employee@enterprise.com', role: 'Staff Access' },
  ]

  const fillDemo = (demoEmail: string) => {
    setEmail(demoEmail)
    setLocalError(null)
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="flex justify-center">
          <div className="w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-xl shadow-indigo-600/10">
            <Building2 className="w-8 h-8" />
          </div>
        </div>
        <h2 className="mt-4 text-center text-2xl font-bold tracking-tight text-white m-0">
          Enterprise Decision Support
        </h2>
        <p className="mt-1 text-center text-sm text-slate-400 m-0">
          Sign in to access HR, Sales, Inventory, and Agentic AI operations
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4 sm:px-0">
        <div className="bg-slate-900/80 backdrop-blur-md py-8 px-6 sm:px-8 border border-slate-800 rounded-2xl shadow-2xl">
          {localError && (
            <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-sm">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-200 m-0">Sign In Error</p>
                <p className="text-xs text-rose-300 mt-0.5 m-0">{localError}</p>
              </div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5"
              >
                Enterprise Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@enterprise.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-950/60 border border-slate-700/80 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-950/60 border border-slate-700/80 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
              className="w-full mt-2"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In to System
            </Button>
          </form>

          {/* Quick Demo Credentials Helper */}
          <div className="mt-8 pt-6 border-t border-slate-800">
            <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <Shield className="w-3.5 h-3.5 text-indigo-400" />
              <span>Demo Role Fillers</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {demoAccounts.map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => fillDemo(acc.email)}
                  className="text-left p-2.5 rounded-lg bg-slate-950/60 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer group"
                >
                  <div className="text-xs font-medium text-slate-200 group-hover:text-indigo-300">
                    {acc.label}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">
                    {acc.role}
                  </div>
                </button>
              ))}
            </div>
            <p className="text-[11px] text-slate-400 text-center mt-3 m-0">
              Select an account role above to pre-fill the email identifier
            </p>
          </div>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6 m-0">
          Protected Enterprise Decision Support System • Strict Backend RBAC
        </p>
      </div>
    </div>
  )
}

export default LoginPage
