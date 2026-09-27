import { useNavigate } from 'react-router-dom'
import { logout } from '../api/client'
import { useAuthStore } from '../store/useAuthStore'

export default function AccountMenu() {
  const account = useAuthStore(s => s.account); const clear = useAuthStore(s => s.clear); const navigate = useNavigate()
  if (!account) return null
  return <div className="account-menu"><span>{account.display_name}</span><button onClick={async () => { await logout(); clear(); navigate('/login') }}>退出</button></div>
}
