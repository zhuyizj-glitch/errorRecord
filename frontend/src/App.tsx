import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from './store/useStore'
import ChildSwitcher from './components/ChildSwitcher'
import SubjectSelector from './components/SubjectSelector'
import UploadPage from './pages/UploadPage'
import ListPage from './pages/ListPage'
import DetailPage from './pages/DetailPage'
import ReviewPage from './pages/ReviewPage'
import SettingsPage from './pages/SettingsPage'
import DashboardPage from './pages/DashboardPage'

function NavLinks() {
  const location = useLocation()
  const links = [
    { path: '/', label: '📷 上传' },
    { path: '/list', label: '📋 列表' },
    { path: '/review', label: '🔄 复习' },
    { path: '/dashboard', label: '📊 统计' },
    { path: '/settings', label: '⚙️ 设置' },
  ]
  return (
    <nav style={{ display: 'flex', gap: '4px' }}>
      {links.map(link => (
        <a
          key={link.path}
          href={link.path}
          onClick={e => { e.preventDefault(); window.history.pushState({}, '', link.path); window.dispatchEvent(new PopStateEvent('popstate')) }}
          style={{
            padding: '8px 16px',
            borderRadius: 'var(--radius-sm)',
            fontWeight: location.pathname === link.path ? 600 : 400,
            background: location.pathname === link.path ? 'var(--color-primary-light)' : 'transparent',
            color: location.pathname === link.path ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            transition: 'all 0.2s',
          }}
        >
          {link.label}
        </a>
      ))}
    </nav>
  )
}

function AppContent() {
  const currentChild = useStore(s => s.currentChild)
  const fetchChildren = useStore(s => s.fetchChildren)

  useEffect(() => {
    fetchChildren()
  }, [fetchChildren])

  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{
        background: 'var(--color-surface)',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        borderBottom: '1px solid var(--color-border)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: 'var(--shadow-sm)',
        flexWrap: 'wrap',
      }}>
        <h1 style={{
          margin: 0,
          fontSize: '20px',
          fontWeight: 700,
          background: 'linear-gradient(135deg, var(--color-primary), #7c4dff)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          📝 错题集
        </h1>
        <div style={{ width: '1px', height: '24px', background: 'var(--color-border)' }} />
        <ChildSwitcher />
        <SubjectSelector />
        <div style={{ marginLeft: 'auto' }}>
          <NavLinks />
        </div>
      </header>

      <main style={{
        padding: '24px',
        maxWidth: '960px',
        margin: '0 auto',
      }}>
        <Routes>
          <Route path="/" element={currentChild ? <UploadPage /> : <EmptyState text="请先选择孩子" />} />
          <Route path="/list" element={currentChild ? <ListPage /> : <EmptyState text="请先选择孩子" />} />
          <Route path="/question/:id" element={currentChild ? <DetailPage /> : <EmptyState text="请先选择孩子" />} />
          <Route path="/review" element={currentChild ? <ReviewPage /> : <EmptyState text="请先选择孩子" />} />
          <Route path="/dashboard" element={currentChild ? <DashboardPage /> : <EmptyState text="请先选择孩子" />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return (
    <div style={{
      textAlign: 'center',
      padding: '80px 20px',
      color: 'var(--color-text-secondary)',
      fontSize: '16px',
    }}>
      <div style={{ fontSize: '48px', marginBottom: '16px' }}>📝</div>
      {text}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
