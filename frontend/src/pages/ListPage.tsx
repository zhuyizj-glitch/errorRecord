/** 错题列表页面 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, BookOpen, Calendar, Inbox, LoaderCircle, RefreshCw, Tag } from 'lucide-react'
import { useStore } from '../store/useStore'
import { fetchQuestions } from '../api/client'
import type { Question } from '../types'

export default function ListPage() {
  const { currentChild, currentSubject, children } = useStore()
  const navigate = useNavigate()
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [filterType, setFilterType] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [moveChild, setMoveChild] = useState('')
  const [moveSubject, setMoveSubject] = useState('')

  useEffect(() => {
    if (!currentChild) return
    setLoading(true)
    fetchQuestions(currentChild, currentSubject || undefined)
      .then(res => setQuestions(res.questions || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [currentChild, currentSubject])

  const handleMove = async (id: string) => {
    // 用这道题自己的归属来定位它，而不是当前筛选条件 ——
    // 「全部」模式下 currentSubject 是空字符串，靠它定位会找不到题
    const target = questions.find(item => item.id === id)
    if (!target || !moveChild || !moveSubject) return

    try {
      const params = new URLSearchParams({
        child_id: target.child_id,
        subject: target.subject,
        new_child_id: moveChild,
        new_subject: moveSubject,
      })
      await fetch(`/api/questions/${id}?${params}`, { method: 'PATCH' })
      // 刷新列表（保持当前筛选条件不变）
      if (currentChild) {
        const res = await fetchQuestions(currentChild, currentSubject || undefined)
        setQuestions(res.questions || [])
      }
      setEditingId(null)
    } catch (e) {
      console.error('Move failed:', e)
    }
  }

  const startEditing = (id: string) => {
    const q = questions.find(q => q.id === id)
    if (q) {
      setMoveChild(q.child_id)
      setMoveSubject(q.subject)
      setEditingId(id)
    }
  }

  const filtered = filterType
    ? questions.filter(q => q.mastery_level === filterType)
    : questions

  const masteryColor = (level: string) => {
    switch (level) {
      case 'low': return '#d32f2f'
      case 'medium': return '#f57c00'
      case 'high': return '#2e7d32'
      default: return '#999'
    }
  }

  const masteryLabel = (level: string) => {
    switch (level) {
      case 'low': return '🔴 薄弱'
      case 'medium': return '🟡 待加强'
      case 'high': return '🟢 已掌握'
      default: return level
    }
  }

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-secondary)' }}>
      <div style={{ marginBottom: '12px' }}>
        <LoaderCircle size={32} color="var(--color-text-tertiary)" />
      </div>
      加载中...
    </div>
  )

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <h2 style={{ margin: 0 }}>错题列表</h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontSize: '13px',
            }}
          >
            <option value="">全部掌握度</option>
            <option value="low">🔴 薄弱</option>
            <option value="medium">🟡 待加强</option>
            <option value="high">🟢 已掌握</option>
          </select>
          <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            共 {filtered.length} 题
          </span>
        </div>
      </div>

      {filtered.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: 'var(--color-text-secondary)',
          background: 'var(--color-surface)',
          borderRadius: 'var(--radius-lg)',
          marginTop: '16px',
        }}>
          <div style={{ marginBottom: '12px' }}>
            <Inbox size={44} strokeWidth={1.2} color="var(--color-text-tertiary)" />
          </div>
          <p>还没有错题，去上传一道吧！</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {filtered.map(q => (
          <div key={q.id}
            onClick={() => {
              // 带上这道题自己的学科，而不是当前筛选的学科 ——
              // 「全部」模式下 currentSubject 是空字符串，传过去详情页会打不开
              navigate(`/question/${q.id}?child_id=${currentChild}&subject=${q.subject}`)
            }}
            style={{
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-md)',
            padding: '16px 20px',
            border: '1px solid var(--color-border)',
            boxShadow: 'var(--shadow-sm)',
            transition: 'box-shadow 0.2s, transform 0.2s',
            cursor: 'pointer',
          }}
          onMouseEnter={e => { e.currentTarget.style.boxShadow = 'var(--shadow-md)'; e.currentTarget.style.transform = 'translateY(-2px)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.transform = 'translateY(0)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <strong style={{ fontSize: '15px' }}>{q.topic}</strong>
                  <span style={{
                    fontSize: '12px',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    background: masteryColor(q.mastery_level) + '18',
                    color: masteryColor(q.mastery_level),
                    fontWeight: 500,
                  }}>
                    {masteryLabel(q.mastery_level)} · {q.mastery_score}分
                  </span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  {q.error_type && (
                    <span><Tag size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />{q.error_type}</span>
                  )}
                  <span><RefreshCw size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />重做 {q.redo_count} 次</span>
                  <span><Calendar size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />{q.error_date}</span>
                </div>
                {q.knowledge_points?.length > 0 && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-tertiary)' }}>
                    <BookOpen size={12} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    {q.knowledge_points.join(' · ')}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={(e) => { e.stopPropagation(); startEditing(q.id) }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-text-tertiary)',
                    fontSize: '14px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                  }}
                  title="移动到其他孩子/学科"
                >
                  <ArrowUpRight size={16} />
                </button>
              </div>
            </div>
            {/* 移动 UI */}
            {editingId === q.id && (
              <div
                onClick={e => e.stopPropagation()}
                style={{
                  marginTop: '12px',
                  padding: '12px',
                  background: 'var(--color-surface-2)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  display: 'flex',
                  gap: '8px',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>移动到：</span>
                <select
                  value={moveChild}
                  onChange={e => setMoveChild(e.target.value)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    fontSize: '13px',
                  }}
                >
                  {children.map(child => (
                    <option key={child.id} value={child.id}>{child.emoji} {child.name}</option>
                  ))}
                </select>
                <select
                  value={moveSubject}
                  onChange={e => setMoveSubject(e.target.value)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    fontSize: '13px',
                  }}
                >
                  {(children.find(child => child.id === moveChild)?.subjects || []).map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button
                  onClick={() => handleMove(q.id)}
                  style={{
                    padding: '4px 12px',
                    background: 'var(--color-primary)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '13px',
                  }}
                >
                  确认移动
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  style={{
                    padding: '4px 12px',
                    background: 'transparent',
                    color: 'var(--color-text-secondary)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '13px',
                  }}
                >
                  取消
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
