import { FormEvent, useState } from 'react'
import { initializeAccount } from '../api/client'
import { useAuthStore } from '../store/useAuthStore'
import { AuthCard } from './LoginPage'

export default function InitializePage() {
  const refresh = useAuthStore(s => s.refresh)
  const [form, setForm] = useState({ username: '', display_name: '', password: '' })
  const [error, setError] = useState('')
  const submit = async (e: FormEvent) => { e.preventDefault(); try { await initializeAccount(form); await refresh() } catch (err: any) { setError(err.response?.data?.detail || '初始化失败') } }
  return <AuthCard title="初始化管理员"><p>首次使用需要创建管理员账号。</p><form onSubmit={submit} className="auth-form">
    <input required placeholder="用户名" onChange={e => setForm({ ...form, username: e.target.value })} />
    <input required placeholder="显示名称" onChange={e => setForm({ ...form, display_name: e.target.value })} />
    <input required type="password" minLength={8} placeholder="密码（至少 8 位）" onChange={e => setForm({ ...form, password: e.target.value })} />
    {error && <p className="form-error">{error}</p>}<button type="submit">创建管理员</button>
  </form></AuthCard>
}
