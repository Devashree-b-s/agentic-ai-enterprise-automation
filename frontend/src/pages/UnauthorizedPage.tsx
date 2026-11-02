import React from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, ArrowLeft, Bot } from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Button from '../components/common/Button'
import Badge from '../components/common/Badge'

export const UnauthorizedPage: React.FC = () => {
  const { user } = useAuthStore()

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mb-6 shadow-xl shadow-rose-500/10">
        <ShieldAlert className="w-8 h-8" />
      </div>

      <Badge variant="danger" size="md" className="mb-3">
        HTTP 403 Forbidden
      </Badge>

      <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight m-0">
        Access Denied
      </h1>
      <p className="text-sm text-slate-400 max-w-md mt-2 m-0 leading-relaxed">
        Your authenticated account (<span className="text-slate-200">{user?.email}</span>) holds the role{' '}
        <span className="text-indigo-400 font-semibold">{user?.role}</span>, which does not have permission to access this protected domain route.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link to="/">
          <Button variant="secondary" size="md" icon={<ArrowLeft className="w-4 h-4" />}>
            Back to Overview
          </Button>
        </Link>
        <Link to="/chat">
          <Button variant="primary" size="md" icon={<Bot className="w-4 h-4" />}>
            Ask AI Assistant
          </Button>
        </Link>
      </div>
    </div>
  )
}

export default UnauthorizedPage
