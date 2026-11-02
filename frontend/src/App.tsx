import React, { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth.store'

// Layout & Protected Route
import DashboardLayout from './components/layout/DashboardLayout'
import ProtectedRoute from './components/layout/ProtectedRoute'

// Pages
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import ChatPage from './pages/ChatPage'
import HRPage from './pages/HRPage'
import SalesPage from './pages/SalesPage'
import InventoryPage from './pages/InventoryPage'
import AdminPage from './pages/AdminPage'
import DocumentsPage from './pages/DocumentsPage'
import ApprovalsPage from './pages/ApprovalsPage'
import PredictionsPage from './pages/PredictionsPage'
import UnauthorizedPage from './pages/UnauthorizedPage'
import NotFoundPage from './pages/NotFoundPage'

export const App: React.FC = () => {
  const initialize = useAuthStore((state) => state.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Authentication Route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected Dashboard Layout */}
        <Route
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          {/* Overview & Common Routes (All authenticated roles) */}
          <Route path="/" element={<OverviewPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/predictions" element={<PredictionsPage />} />

          {/* HR Route (Admin, Manager, HR) */}
          <Route
            path="/hr"
            element={
              <ProtectedRoute allowedRoles={['Admin', 'Manager', 'HR']}>
                <HRPage />
              </ProtectedRoute>
            }
          />

          {/* Sales Route (Admin, Manager) */}
          <Route
            path="/sales"
            element={
              <ProtectedRoute allowedRoles={['Admin', 'Manager']}>
                <SalesPage />
              </ProtectedRoute>
            }
          />

          {/* Admin Route (Admin only) */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['Admin']}>
                <AdminPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Utility Status Routes */}
        <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
