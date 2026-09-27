import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from './store/useStore'
import { useAuthStore } from './store/useAuthStore'
import ChildSwitcher from './components/ChildSwitcher'
import SubjectSelector from './components/SubjectSelector'
import AccountMenu from './components/AccountMenu'
import UploadPage from './pages/UploadPage'
import ListPage from './pages/ListPage'
import DetailPage from './pages/DetailPage'
import ReviewPage from './pages/ReviewPage'
import SettingsPage from './pages/SettingsPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import InitializePage from './pages/InitializePage'
import ChangePasswordPage from './pages/ChangePasswordPage'
import ChildrenPage from './pages/ChildrenPage'
import AdminPage from './pages/AdminPage'

function Workspace() {
  const account = useAuthStore(s => s.account)
  const currentChild = useStore(s => s.currentChild)
  const fetchChildren = useStore(s => s.fetchChildren)
  useEffect(() => { fetchChildren() }, [fetchChildren])
  const links = [['/', '📷 上传'], ['/list', '📋 列表'], ['/review', '🔄 复习'], ['/dashboard', '📊 统计'], ['/children', '👶 孩子']]
  if (account?.role === 'admin') links.push(['/settings', '⚙️ 设置'], ['/admin', '🛡️ 管理'])
  const childPage = (page: React.ReactNode) => currentChild ? page : <EmptyState />
  return <div className="app"><header><h1>📝 错题集</h1><ChildSwitcher/><SubjectSelector/><nav>{links.map(([path,label]) => <NavLink key={path} to={path}>{label}</NavLink>)}</nav><AccountMenu/></header><main><Routes>
    <Route path="/" element={childPage(<UploadPage/>)} /><Route path="/list" element={childPage(<ListPage/>)} /><Route path="/question/:id" element={childPage(<DetailPage/>)} /><Route path="/review" element={childPage(<ReviewPage/>)} /><Route path="/dashboard" element={childPage(<DashboardPage/>)} /><Route path="/children" element={<ChildrenPage/>} />
    <Route path="/settings" element={account?.role === 'admin' ? <SettingsPage/> : <Navigate to="/"/>} /><Route path="/admin" element={account?.role === 'admin' ? <AdminPage/> : <Navigate to="/"/>} />
  </Routes></main></div>
}
function EmptyState(){ return <div className="empty-state">👶<br/>请先在“孩子”页面创建孩子和课程</div> }
function Gate() {
  const { loading, initialized, account, refresh } = useAuthStore()
  useEffect(() => { refresh() }, [refresh])
  if (loading || initialized === null) return <div className="loading">正在加载…</div>
  if (!initialized) return <Routes><Route path="*" element={<InitializePage/>}/></Routes>
  if (!account) return <Routes><Route path="/register" element={<RegisterPage/>}/><Route path="*" element={<LoginPage/>}/></Routes>
  if (account.must_change_password) return <Routes><Route path="*" element={<ChangePasswordPage/>}/></Routes>
  return <Workspace/>
}
export default function App(){ return <BrowserRouter><Gate/></BrowserRouter> }
