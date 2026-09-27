/** 学科选择组件 */

import { useStore } from '../store/useStore'
import { useEffect, useMemo } from 'react'

export default function SubjectSelector() {
  const children = useStore(s => s.children)
  const currentChild = useStore(s => s.currentChild)
  const currentSubject = useStore(s => s.currentSubject)
  const setSubject = useStore(s => s.setSubject)

  const subjects = useMemo(() =>
    children.find(child => child.id === currentChild)?.subjects || [],
    [children, currentChild]
  )

  useEffect(() => {
    if (subjects.length > 0) {
      setSubject(subjects[0])
    }
  }, [currentChild, subjects.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!subjects.length) return null

  return (
    <select
      value={currentSubject || ''}
      onChange={e => setSubject(e.target.value)}
      style={{
        padding: '6px 12px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--color-border)',
        fontSize: '13px',
        color: 'var(--color-text)',
        background: 'var(--color-surface)',
        cursor: 'pointer',
      }}
    >
      {subjects.map(s => (
        <option key={s} value={s}>{s}</option>
      ))}
    </select>
  )
}
