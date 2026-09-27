import { useEffect, useState } from 'react'
import { createInvite, fetchAccounts, fetchInvites, resetAccountPassword, revokeInvite } from '../api/client'

export default function AdminPage() {
  const [invites, setInvites] = useState<any[]>([]); const [accounts, setAccounts] = useState<any[]>([]); const [secret, setSecret] = useState('')
  const load = async () => { const [i, a] = await Promise.all([fetchInvites(), fetchAccounts()]); setInvites(i.invites); setAccounts(a.accounts) }
  useEffect(() => { load().catch(console.error) }, [])
  return <div><h2>🛡️ 账号管理</h2>{secret && <div className="one-time-secret">请立即复制，本页只显示一次：<strong>{secret}</strong></div>}<section className="panel"><h3>邀请码</h3><button onClick={async () => { const r = await createInvite(); setSecret(r.code); await load() }}>生成 7 天邀请码</button>{invites.map(i => <div className="admin-row" key={i.id}><span>{i.status || '可用'} · {i.expires_at}</span>{!i.used_at && !i.revoked_at && <button className="secondary" onClick={async () => { await revokeInvite(i.id); await load() }}>作废</button>}</div>)}</section><section className="panel"><h3>账号</h3>{accounts.map(a => <div className="admin-row" key={a.id}><span><strong>{a.display_name}</strong> @{a.username} · {a.role}</span><button className="secondary" onClick={async () => { const r = await resetAccountPassword(a.id); setSecret(r.temporary_password); await load() }}>重置密码</button></div>)}</section></div>
}
