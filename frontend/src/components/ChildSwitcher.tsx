/** 孩子切换组件 */

import { useStore } from '../store/useStore'

export default function ChildSwitcher() {
  const children = useStore(s => s.children)
  const currentChild = useStore(s => s.currentChild)
  const setChild = useStore(s => s.setChild)
  const entries = Object.entries(children)

  if (entries.length === 0) return <span style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>加载中...</span>

  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      {entries.map(([key, child]) => (
        <button
          key={key}
          onClick={() => setChild(key)}
          style={{
            padding: '6px 14px',
            borderRadius: '20px',
            border: currentChild === key ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
            background: currentChild === key ? 'var(--color-primary-light)' : 'var(--color-surface)',
            color: currentChild === key ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            cursor: 'pointer',
            fontWeight: currentChild === key ? 600 : 400,
            fontSize: '13px',
            transition: 'all 0.2s',
          }}
        >
          {child.emoji} {child.name}
        </button>
      ))}
    </div>
  )
}
