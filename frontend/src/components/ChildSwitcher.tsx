/** 孩子切换组件 */

import { useStore } from '../store/useStore'

export default function ChildSwitcher() {
  const children = useStore(s => s.children)
  const currentChild = useStore(s => s.currentChild)
  const setChild = useStore(s => s.setChild)
  if (children.length === 0) return <span style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>请先创建孩子</span>

  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      {children.map(child => (
        <button
          key={child.id}
          onClick={() => setChild(child.id)}
          style={{
            padding: '6px 14px',
            borderRadius: '20px',
            border: currentChild === child.id ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
            background: currentChild === child.id ? 'var(--color-primary-light)' : 'var(--color-surface)',
            color: currentChild === child.id ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            cursor: 'pointer',
            fontWeight: currentChild === child.id ? 600 : 400,
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
