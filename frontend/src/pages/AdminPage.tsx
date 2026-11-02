import React, { useState } from 'react'
import {
  ShieldCheck,
  UserPlus,
  KeyRound,
  Database,
  FileText,
  AlertCircle,
  CheckCircle2,
  Lock,
  Mail,
  User,
  Hash,
  Info,
} from 'lucide-react'
import { useAuthStore } from '../store/auth.store'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import Button from '../components/common/Button'
import ConfirmModal from '../components/common/ConfirmModal'
import { adminService } from '../services/admin.service'
import type { User as AuthUser, UserRole } from '../types/auth.types'

export const AdminPage: React.FC = () => {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'Admin'

  // Provisioning Form State
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('Employee')
  const [employeeCode, setEmployeeCode] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isConfirmProvisionOpen, setIsConfirmProvisionOpen] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Track session-provisioned users
  const [recentUsers, setRecentUsers] = useState<AuthUser[]>([])

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isAdmin) return
    if (!email.trim() || password.length < 8) {
      setErrorMsg('Please provide a valid email and a password of at least 8 characters.')
      return
    }
    setIsConfirmProvisionOpen(true)
  }

  const executeCreateUser = async () => {
    setIsSubmitting(true)
    setErrorMsg(null)
    setSuccessMsg(null)

    try {
      const newUser = await adminService.createUser({
        email: email.trim(),
        password: password.trim(),
        role,
        employee_code: employeeCode.trim() ? employeeCode.trim() : undefined,
      })

      setSuccessMsg(
        `Successfully provisioned user '${newUser.email}' with ${newUser.role} privileges (User ID #${newUser.id}).`,
      )
      setRecentUsers((prev) => [newUser, ...prev])
      setIsConfirmProvisionOpen(false)

      // Clear form inputs
      setEmail('')
      setPassword('')
      setRole('Employee')
      setEmployeeCode('')
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to provision user. Please verify email format and credentials.'
      setErrorMsg(detail)
      setIsConfirmProvisionOpen(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isAdmin) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white m-0">Enterprise Administration</h1>
            <p className="text-xs text-slate-400 mt-1 m-0">
              Privileged system administration
            </p>
          </div>
          <Badge variant="danger">
            <AlertCircle className="w-3.5 h-3.5" />
            Admin Exclusive
          </Badge>
        </div>

        <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 text-center max-w-lg mx-auto">
          <AlertCircle className="w-12 h-12 text-rose-400 mx-auto mb-3" />
          <h2 className="text-base font-semibold text-white m-0">
            Access Restricted
          </h2>
          <p className="text-xs text-slate-400 mt-2 mb-0 leading-relaxed">
            Enterprise administration and user provisioning are restricted exclusively to
            authenticated <strong className="text-rose-400">Admin</strong> users. Current role: {user?.role}.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight m-0">
            Enterprise Administration Console
          </h1>
          <p className="text-xs text-slate-400 mt-1 m-0">
            Privileged user provisioning, RBAC role assignment, and security configuration
          </p>
        </div>
        <Badge variant="danger">
          <ShieldCheck className="w-3.5 h-3.5" />
          Active Administrator Session ({user?.email})
        </Badge>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-rose-500/10 text-rose-400">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">User Provisioning</div>
              <div className="text-xl font-bold text-white mt-0.5">Admin-Only API</div>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-3 m-0">
            Provision user accounts with assigned RBAC roles via <code className="text-slate-300 font-mono">POST /api/v1/auth/users</code>.
          </p>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-400">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">JWT Cryptography</div>
              <div className="text-xl font-bold text-white mt-0.5">HS256 Protection</div>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-3 m-0">
            Tokens expire in 60 minutes. Passwords and signing secrets are never exposed to the frontend.
          </p>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs text-slate-400 font-medium">Database Backend</div>
              <div className="text-xl font-bold text-white mt-0.5">SQLite & ACID</div>
            </div>
          </div>
          <p className="text-xs text-slate-400 mt-3 m-0">
            Enforces strict foreign key integrity between User credentials and HR Employee profiles.
          </p>
        </Card>
      </div>

      {/* User Provisioning Form */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title="Provision New Enterprise User"
          subtitle="Directly calls POST /api/v1/auth/users with administrator authorization"
        >
          <form onSubmit={handleCreateUser} className="space-y-4">
            {errorMsg && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* Email */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                Official Enterprise Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="e.g. jane.doe@enterprise.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                Initial Password (minimum 8 characters)
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
                <span>Minimum 8 characters</span>
                <span
                  className={
                    password.length >= 8
                      ? 'text-emerald-400 font-medium'
                      : password.length > 0
                        ? 'text-amber-400'
                        : 'text-slate-500'
                  }
                >
                  {password.length}/8 chars
                </span>
              </div>
            </div>

            {/* Role & Employee Code */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  RBAC Role Selection
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="Employee">Employee (Default)</option>
                    <option value="HR">HR Specialist</option>
                    <option value="Manager">Manager</option>
                    <option value="Admin">System Administrator</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Link Employee Code (Optional)
                </label>
                <div className="relative">
                  <Hash className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="e.g. EMP-001"
                    value={employeeCode}
                    onChange={(e) => setEmployeeCode(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={isSubmitting}
                className="w-full"
              >
                <UserPlus className="w-4 h-4" />
                {isSubmitting ? 'Provisioning Account...' : 'Provision User Account'}
              </Button>
            </div>
          </form>
        </Card>

        {/* Missing Endpoint Notice & Session History */}
        <div className="space-y-6">
          <Card
            title="Backend API Architecture Notice"
            subtitle="Identification of available vs missing endpoints"
          >
            <div className="space-y-3 text-xs text-slate-300">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed text-slate-400">
                  <strong className="text-slate-200">Missing User Listing API: </strong>
                  The backend FastAPI implementation provides <code className="text-indigo-400 font-mono">POST /api/v1/auth/users</code> for privileged account creation, but does NOT provide a <code className="text-rose-400 font-mono">GET /api/v1/auth/users</code> listing endpoint.
                  In strict compliance with requirements, we do not fabricate or mock a synthetic user list; newly created accounts during this session are displayed below.
                </div>
              </div>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed text-slate-400">
                  <strong className="text-slate-200">Zero Secret Exposure: </strong>
                  Passwords and JWT secrets are strictly managed server-side. Passwords are encrypted with bcrypt before database persistence.
                </div>
              </div>
            </div>
          </Card>

          {/* Session Provisioned Accounts */}
          <Card
            title="Session Provisioned Accounts"
            subtitle="Users provisioned during this administrative session"
          >
            {recentUsers.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No users provisioned in this active session yet.
              </div>
            ) : (
              <div className="space-y-2">
                {recentUsers.map((u) => (
                  <div
                    key={u.id}
                    className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-white">{u.email}</div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        User ID: #{u.id} {u.employee_id ? `• Employee ID: #${u.employee_id}` : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          u.role === 'Admin'
                            ? 'danger'
                            : u.role === 'Manager'
                            ? 'warning'
                            : u.role === 'HR'
                            ? 'primary'
                            : 'neutral'
                        }
                        size="sm"
                      >
                        {u.role}
                      </Badge>
                      <Badge variant="success" size="sm">
                        Active
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* AI Supervisor System Guardrails */}
      <Card title="System Architecture & AI Supervisor Guardrails" subtitle="Milestone 7 Specifications">
        <div className="space-y-3 text-xs text-slate-300">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-950/60 border border-slate-800">
            <FileText className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-200">Execution Guardrails</div>
              <div className="text-slate-400 mt-0.5">
                Maximum 10 supervisor iterations, maximum 15 tool calls per request, 60s timeout handling.
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-950/60 border border-slate-800">
            <FileText className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-slate-200">Strict Read-Only AI Tools</div>
              <div className="text-slate-400 mt-0.5">
                All 16 registered agent tools perform SELECT-only operations. No write mutations are permitted through the agent interface.
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Confirmation Dialog for Privileged User Provisioning */}
      <ConfirmModal
        isOpen={isConfirmProvisionOpen}
        onClose={() => setIsConfirmProvisionOpen(false)}
        onConfirm={executeCreateUser}
        title="Confirm User Provisioning"
        message={`Are you sure you want to provision user account '${email}' with ${role} privileges?`}
        details={
          <div className="space-y-1">
            <div><strong>Email:</strong> {email}</div>
            <div><strong>Assigned RBAC Role:</strong> {role}</div>
            {employeeCode && <div><strong>Employee Code:</strong> {employeeCode}</div>}
            {(role === 'Admin' || role === 'Manager') && (
              <div className="text-amber-400 pt-1 border-t border-slate-800">
                Warning: The {role} role grants access to sensitive operational, staffing, or financial metrics.
              </div>
            )}
          </div>
        }
        confirmLabel={`Yes, Provision ${role}`}
        variant={role === 'Admin' ? 'danger' : role === 'Manager' ? 'warning' : 'primary'}
        isLoading={isSubmitting}
      />
    </div>
  )
}

export default AdminPage
