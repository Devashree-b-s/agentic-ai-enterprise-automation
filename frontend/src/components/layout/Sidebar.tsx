import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  TrendingUp,
  LineChart,
  Package,
  Bot,
  FileText,
  CheckSquare,
  ShieldCheck,
  Building2,
  LogOut,
  X,
} from 'lucide-react'
import { useAuthStore } from '../../store/auth.store'
import type { UserRole } from '../../types/auth.types'
import Badge from '../common/Badge'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  roles?: UserRole[]
  description: string
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user, logout } = useAuthStore()

  const navItems: NavItem[] = [
    {
      label: 'Overview',
      path: '/',
      icon: <LayoutDashboard className="w-5 h-5" />,
      description: 'Executive dashboard & KPIs',
    },
    {
      label: 'AI Decision Assistant',
      path: '/chat',
      icon: <Bot className="w-5 h-5 text-indigo-400" />,
      description: 'LangGraph decision agent',
    },
    {
      label: 'Document Intelligence',
      path: '/documents',
      icon: <FileText className="w-5 h-5 text-cyan-400" />,
      roles: ['Admin', 'Manager', 'HR', 'Employee'],
      description: 'Enterprise RAG & vector store',
    },
    {
      label: 'Approvals & Workflows',
      path: '/approvals',
      icon: <CheckSquare className="w-5 h-5 text-amber-400" />,
      roles: ['Admin', 'Manager', 'HR', 'Employee'],
      description: 'Human-in-the-loop decisions',
    },
    {
      label: 'Predictive Analytics',
      path: '/predictions',
      icon: <LineChart className="w-5 h-5 text-emerald-400" />,
      roles: ['Admin', 'Manager', 'HR', 'Employee'],
      description: 'Forecasts & risk modeling',
    },
    {
      label: 'HR & Staffing',
      path: '/hr',
      icon: <Users className="w-5 h-5" />,
      roles: ['Admin', 'Manager', 'HR'],
      description: 'Staff & leave requests',
    },
    {
      label: 'Sales & Revenue',
      path: '/sales',
      icon: <TrendingUp className="w-5 h-5" />,
      roles: ['Admin', 'Manager'],
      description: 'Revenue recognition & orders',
    },
    {
      label: 'Inventory & Stock',
      path: '/inventory',
      icon: <Package className="w-5 h-5" />,
      roles: ['Admin', 'Manager', 'HR', 'Employee'],
      description: 'Warehouse stock & alerts',
    },
    {
      label: 'Administration',
      path: '/admin',
      icon: <ShieldCheck className="w-5 h-5" />,
      roles: ['Admin'],
      description: 'System roles & audit',
    },
  ]

  const userRole = user?.role || 'Employee'

  // Filter navigation items by role
  const visibleNavItems = navItems.filter(
    (item) => !item.roles || item.roles.includes(userRole),
  )

  const roleBadgeVariant: Record<UserRole, 'primary' | 'success' | 'warning' | 'danger'> = {
    Admin: 'danger',
    Manager: 'primary',
    HR: 'warning',
    Employee: 'success',
  }

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-slate-900 border-r border-slate-800/80 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand header */}
        <div className="h-16 px-6 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-white m-0">
                Enterprise AI
              </h1>
              <p className="text-[10px] uppercase tracking-wider text-slate-400 font-medium m-0">
                Decision Support
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden text-slate-400 hover:text-white p-1 rounded-md hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Navigation
          </div>

          {visibleNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30 shadow-xs'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`
              }
            >
              {item.icon}
              <div className="flex-1 truncate">
                <div>{item.label}</div>
                <div className="text-[11px] text-slate-400 font-normal truncate">
                  {item.description}
                </div>
              </div>
            </NavLink>
          ))}
        </div>

        {/* User profile footer */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3 truncate">
              <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-semibold text-slate-200">
                {user?.email?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="truncate">
                <div className="text-xs font-medium text-slate-200 truncate">
                  {user?.email || 'Authenticated User'}
                </div>
                <div className="mt-0.5">
                  <Badge variant={roleBadgeVariant[userRole]} size="sm">
                    {userRole}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={() => logout()}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg border border-slate-800 hover:border-rose-500/20 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
