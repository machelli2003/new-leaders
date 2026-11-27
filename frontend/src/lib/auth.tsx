import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, refreshSession, setAccessToken } from './api'

export type User = { id: string; name: string; email: string; role: string; role_label: string; permissions: string[]; must_change_password?: boolean; mfa_enabled?: boolean; mfa_required?: boolean }
type LoginResult = { user: User; mfaEnrollmentRequired: boolean }
type Ctx = {
  user: User | null; loading: boolean
  login: (email: string, password: string, opts?: { otp?: string; superAdmin?: boolean }) => Promise<LoginResult>
  logout: () => Promise<void>; can: (p: string) => boolean; reload: () => Promise<void>
}
const C = createContext<Ctx>(null as any)
export const useAuth = () => useContext(C)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    refreshSession().then((d) => { if (d) setUser(d.user) }).finally(() => setLoading(false))
  }, [])
  const login: Ctx['login'] = async (email, password, opts) => {
    const path = opts?.superAdmin ? '/auth/super-admin/login' : '/auth/login'
    const d = await api(path, { body: { email, password, otp: opts?.otp || undefined }, auth: false })
    setAccessToken(d.access_token); setUser(d.user)
    return { user: d.user, mfaEnrollmentRequired: !!d.mfa_enrollment_required }
  }
  const logout = async () => { try { await api('/auth/logout', { method: 'POST' }) } catch { /* ignore */ } setAccessToken(null); setUser(null) }
  const reload = useCallback(async () => { setUser(await api('/auth/me')) }, [])
  const can = (p: string) => !!user?.permissions.includes(p)
  return <C.Provider value={{ user, loading, login, logout, can, reload }}>{children}</C.Provider>
}

/** UX guard only. The API enforces every permission server-side. */
export function RequireAuth({ children, perm, superAdmin }: { children: ReactNode; perm?: string; superAdmin?: boolean }) {
  const { user, loading, can } = useAuth()
  const loc = useLocation()
  if (loading) return null
  if (!user) return <Navigate to={superAdmin ? '/super-admin/login' : '/admin/login'} state={{ from: loc.pathname }} replace />
  if (superAdmin && user.role !== 'super_admin') return <Navigate to="/admin/dashboard" replace />
  if (user.must_change_password && loc.pathname !== '/admin/change-password') return <Navigate to="/admin/change-password" replace />
  if (user.role === 'super_admin' && user.mfa_required && !user.mfa_enabled && loc.pathname !== '/super-admin/mfa-setup') {
    return <Navigate to="/super-admin/mfa-setup" replace />
  }
  if (perm && !can(perm)) return <div className="p-10 text-center"><h2 className="text-lg font-semibold">Access denied</h2><p className="text-sm text-[var(--muted)]">You do not have permission to view this page.</p></div>
  return <>{children}</>
}
