import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useEffect } from 'react'
import {
  Baby,
  BarChart3,
  BookOpen,
  Camera,
  ListChecks,
  RefreshCw,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
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

/** 导航项：[路由, 名称, 图标组件] */
type NavItem = [path: string, label: string, Icon: LucideIcon]

function Workspace() {
  const account = useAuthStore(s => s.account)
  const currentChild = useStore(s => s.currentChild)
  const fetchChildren = useStore(s => s.fetchChildren)
  useEffect(() => { fetchChildren() }, [fetchChildren])

  const links: NavItem[] = [
    ['/', '上传', Camera],
    ['/list', '列表', ListChecks],
    ['/review', '复习', RefreshCw],
    ['/dashboard', '统计', BarChart3],
    ['/children', '孩子', Baby],
  ]
  if (account?.role === 'admin') {
    links.push(['/settings', '设置', Settings], ['/admin', '管理', ShieldCheck])
  }

  const childPage = (page: React.ReactNode) => currentChild ? page : <EmptyState />

  return (
    <div className="app">
      <header>
        <h1>
          <BookOpen size={18} strokeWidth={2.4} style={{ verticalAlign: '-3px', marginRight: 6 }} />
          错题集
        </h1>
        <ChildSwitcher />
        <SubjectSelector />
        <nav>
          {links.map(([path, label, Icon]) => (
            <NavLink key={path} to={path}>
              <Icon size={16} strokeWidth={2.2} />
              {label}
            </NavLink>
          ))}
        </nav>
        <AccountMenu />
      </header>
      <main>
        <Routes>
          <Route path="/" element={childPage(<UploadPage />)} />
          <Route path="/list" element={childPage(<ListPage />)} />
          <Route path="/question/:id" element={childPage(<DetailPage />)} />
          <Route path="/review" element={childPage(<ReviewPage />)} />
          <Route path="/dashboard" element={childPage(<DashboardPage />)} />
          <Route path="/children" element={<ChildrenPage />} />
          <Route path="/settings" element={account?.role === 'admin' ? <SettingsPage /> : <Navigate to="/" />} />
          <Route path="/admin" element={account?.role === 'admin' ? <AdminPage /> : <Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="empty-state">
      <Baby size={40} strokeWidth={1.5} />
      <span>请先在「孩子」页面创建孩子和课程</span>
    </div>
  )
}

function Gate() {
  const { loading, initialized, account, refresh } = useAuthStore()
  useEffect(() => { refresh() }, [refresh])
  if (loading || initialized === null) return <div className="loading">正在加载…</div>
  if (!initialized) return <Routes><Route path="*" element={<InitializePage />} /></Routes>
  if (!account) return <Routes><Route path="/register" element={<RegisterPage />} /><Route path="*" element={<LoginPage />} /></Routes>
  if (account.must_change_password) return <Routes><Route path="*" element={<ChangePasswordPage />} /></Routes>
  return <Workspace />
}

export default function App() { return <BrowserRouter><Gate /></BrowserRouter> }
