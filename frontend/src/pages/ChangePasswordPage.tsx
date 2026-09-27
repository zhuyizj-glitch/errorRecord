import { FormEvent, useState } from 'react'
import { changePassword } from '../api/client'
import { useAuthStore } from '../store/useAuthStore'
import { AuthCard } from './LoginPage'

export default function ChangePasswordPage() {
  const refresh = useAuthStore(s => s.refresh)
  const [current_password, setCurrent] = useState(''); const [new_password, setNext] = useState(''); const [error, setError] = useState('')
  const submit = async (e: FormEvent) => { e.preventDefault(); try { await changePassword({ current_password, new_password }); await refresh() } catch (err: any) { setError(err.response?.data?.detail || '修改失败') } }
  return <AuthCard title="修改密码"><p>管理员已重置密码，请先设置你自己的新密码。</p><form onSubmit={submit} className="auth-form">
    <input required type="password" placeholder="当前临时密码" value={current_password} onChange={e => setCurrent(e.target.value)} />
    <input required type="password" minLength={8} placeholder="新密码" value={new_password} onChange={e => setNext(e.target.value)} />
    {error && <p className="form-error">{error}</p>}<button type="submit">保存新密码</button>
  </form></AuthCard>
}
