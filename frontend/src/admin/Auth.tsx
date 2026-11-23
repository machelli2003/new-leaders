import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { api, errMsg } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/form'
import { Card, CardBody } from '@/components/ui/ui'
import { Seo } from '@/components/Seo'

export function Login({ superAdmin }: { superAdmin?: boolean }) {
  const { login, user } = useAuth()
  const nav = useNavigate()
  const loc = useLocation() as any
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [otp, setOtp] = useState('')
  const [needOtp, setNeedOtp] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const home = superAdmin ? '/super-admin/dashboard' : '/admin/dashboard'
  if (user) return <Navigate to={user.must_change_password ? '/admin/change-password' : home} replace />
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try {
      const u = await login(email.trim(), password, { otp, superAdmin })
      nav(u.must_change_password ? '/admin/change-password' : loc.state?.from ?? home, { replace: true })
    } catch (x: any) {
      if (/otp|code|mfa/i.test(errMsg(x)) && superAdmin) setNeedOtp(true)
      setErr(errMsg(x))
    } finally { setBusy(false) }
  }
  return (<div className="grid min-h-screen place-items-center bg-[var(--soft)] p-4"><Seo title={superAdmin ? 'Super Admin sign in' : 'Staff sign in'} noindex />
    <Card className="w-full max-w-sm"><CardBody className="space-y-5">
      <div className="text-center"><ShieldCheck className="mx-auto h-9 w-9 text-[var(--primary)]" /><h1 className="mt-2 text-2xl font-semibold">{superAdmin ? 'Super Admin' : 'Staff sign in'}</h1><p className="text-sm text-[var(--muted)]">New Leaders Hotel & Events Centre</p></div>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email"><Input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {(needOtp || superAdmin) && <Field label="Authenticator code" hint={needOtp ? undefined : 'Only if two-factor is enabled'}><Input inputMode="numeric" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value)} /></Field>}
        {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
        <Button className="w-full" loading={busy}>Sign in</Button></form></CardBody></Card></div>)
}

export function ChangePassword() {
  const { user, reload } = useAuth(); const nav = useNavigate()
  const [cur, setCur] = useState(''); const [pw, setPw] = useState(''); const [pw2, setPw2] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pw !== pw2) return toast.error('Passwords do not match')
    setBusy(true)
    try { await api('/auth/change-password', { body: { current_password: cur, new_password: pw } }); await reload(); toast.success('Password updated'); nav(user?.role === 'super_admin' ? '/super-admin/dashboard' : '/admin/dashboard') }
    catch (x) { toast.error(errMsg(x)) } finally { setBusy(false) }
  }
  return (<div className="grid min-h-screen place-items-center bg-[var(--soft)] p-4"><Card className="w-full max-w-sm"><CardBody>
    <h1 className="mb-1 text-xl font-semibold">Change password</h1>{user?.must_change_password && <p className="mb-3 text-sm text-amber-700">You must set a new password before continuing.</p>}
    <form onSubmit={submit} className="space-y-4">
      <Field label="Current password"><Input type="password" required value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
      <Field label="New password" hint="At least 10 characters, with letters and numbers"><Input type="password" required minLength={10} value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
      <Field label="Confirm new password"><Input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} /></Field>
      <Button className="w-full" loading={busy}>Update password</Button></form></CardBody></Card></div>)
}
