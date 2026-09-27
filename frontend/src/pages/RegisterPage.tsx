import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { register } from '../api/client'
import { useAuthStore } from '../store/useAuthStore'
import { AuthCard } from './LoginPage'

export default function RegisterPage() {
  const refresh = useAuthStore(s => s.refresh)
  const [form, setForm] = useState({ invite_code: '', username: '', display_name: '', password: '' })
  const [error, setError] = useState('')
  const field = (name: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [name]: e.target.value })
  const submit = async (e: FormEvent) => { e.preventDefault(); try { await register(form); await refresh() } catch (err: any) { setError(err.response?.data?.detail || '注册失败') } }
  return <AuthCard title="邀请注册"><form onSubmit={submit} className="auth-form">
    <input required placeholder="一次性邀请码" onChange={field('invite_code')} />
    <input required placeholder="用户名" onChange={field('username')} /><input required placeholder="显示名称" onChange={field('display_name')} />
    <input required type="password" minLength={8} placeholder="密码（至少 8 位）" onChange={field('password')} />
    {error && <p className="form-error">{error}</p>}<button type="submit">注册</button><Link to="/login">返回登录</Link>
  </form></AuthCard>
}
