import React, { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

const routeTitles: Record<string, { title: string; subtitle: string }> = {
  '/': {
    title: 'Enterprise Overview',
    subtitle: 'High-level synthesis across workforce, revenue, and inventory',
  },
  '/chat': {
    title: 'AI Decision Support Assistant',
    subtitle: 'Supervisor agent orchestration over 16 read-only business tools',
  },
  '/hr': {
    title: 'Human Resources & Staffing',
    subtitle: 'Active workforce distribution, department staffing, and leave tracking',
  },
  '/sales': {
    title: 'Sales & Revenue Analytics',
    subtitle: 'Recognized revenue performance, order trends, and top products',
  },
  '/inventory': {
    title: 'Inventory & Warehouse Stock',
    subtitle: 'Stock on hand, replenishment alerts, and product availability',
  },
  '/admin': {
    title: 'Enterprise Administration',
    subtitle: 'User provisioning, RBAC privileges, and security controls',
  },
}

export const DashboardLayout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const location = useLocation()

  const currentRouteMeta = routeTitles[location.pathname] || {
    title: 'Enterprise Dashboard',
    subtitle: 'Agentic Decision Support System',
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="lg:pl-72 flex-1 flex flex-col min-w-0">
        <Header
          onMenuClick={() => setIsSidebarOpen(true)}
          title={currentRouteMeta.title}
          subtitle={currentRouteMeta.subtitle}
        />

        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout
