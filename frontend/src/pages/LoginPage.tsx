import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api/client'
import { useAuthStore } from '../store/useAuthStore'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const refresh = useAuthStore(s => s.refresh)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try { await login({ username, password }); await refresh(); navigate('/') }
    catch (err: any) { setError(err.response?.data?.detail || '登录失败') }
  }
  return <AuthCard title="登录错题集"><form onSubmit={submit} className="auth-form">
    <input required value={username} onChange={e => setUsername(e.target.value)} placeholder="用户名" />
    <input required type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="密码" />
    {error && <p className="form-error">{error}</p>}<button type="submit">登录</button>
    <Link to="/register">有邀请码？注册账号</Link>
  </form></AuthCard>
}

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <main className="auth-shell"><section className="auth-card"><h1>📝 {title}</h1>{children}</section></main>
}
