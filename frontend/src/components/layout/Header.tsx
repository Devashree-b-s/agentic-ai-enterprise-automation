import React from 'react'
import { Menu, Activity, Shield } from 'lucide-react'
import { useAuthStore } from '../../store/auth.store'
import Badge from '../common/Badge'

interface HeaderProps {
  onMenuClick: () => void
  title: string
  subtitle?: string
}

export const Header: React.FC<HeaderProps> = ({
  onMenuClick,
  title,
  subtitle,
}) => {
  const { user } = useAuthStore()

  return (
    <header className="h-16 px-6 bg-slate-900/60 backdrop-blur-md border-b border-slate-800/80 sticky top-0 z-30 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="lg:hidden text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 focus:outline-none"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h2 className="text-base font-semibold text-slate-100 m-0 leading-tight">
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-slate-400 m-0 leading-tight">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Live system health status badge */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-slate-800/50 border border-slate-700/50 rounded-full text-xs text-slate-300">
          <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          <span>Backend Connected</span>
        </div>

        {/* User Role Badge */}
        {user && (
          <div className="hidden md:flex items-center gap-2">
            <Badge variant="neutral" size="sm">
              <Shield className="w-3 h-3 text-slate-400" />
              Role: {user.role}
            </Badge>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header
