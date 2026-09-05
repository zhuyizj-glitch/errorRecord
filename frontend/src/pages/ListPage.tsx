/** 错题列表页面 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store/useStore'
import { fetchQuestions, deleteQuestion } from '../api/client'
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

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除这道错题吗？')) return
    if (!currentChild || !currentSubject) return
    await deleteQuestion(id, currentChild, currentSubject)
    setQuestions(prev => prev.filter(q => q.id !== id))
  }

  const handleMove = async (id: string) => {
    if (!currentChild || !currentSubject) return
    if (!moveChild || !moveSubject) return

    try {
      const params = new URLSearchParams({
        child: currentChild,
        subject: currentSubject,
        new_child: moveChild,
        new_subject: moveSubject,
      })
      await fetch(`/api/questions/${id}?${params}`, { method: 'PATCH' })
      // 刷新列表
      const res = await fetchQuestions(currentChild, currentSubject)
      setQuestions(res.questions || [])
      setEditingId(null)
    } catch (e) {
      console.error('Move failed:', e)
    }
  }

  const startEditing = (id: string) => {
    const q = questions.find(q => q.id === id)
    if (q) {
      setMoveChild(q.child)
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
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
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
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>📭</div>
          <p>还没有错题，去上传一道吧！</p>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
        {filtered.map(q => (
          <div key={q.id}
            onClick={() => navigate(`/question/${q.id}?child=${currentChild}&subject=${currentSubject}`)}
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
                  {q.error_type && <span>🏷 {q.error_type}</span>}
                  <span>🔄 重做 {q.redo_count} 次</span>
                  <span>📅 {q.error_date}</span>
                </div>
                {q.knowledge_points?.length > 0 && (
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#999' }}>
                    📚 {q.knowledge_points.join(' · ')}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={(e) => { e.stopPropagation(); startEditing(q.id) }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#999',
                    fontSize: '14px',
                    padding: '4px 8px',
                    cursor: 'pointer',
                  }}
                  title="移动到其他孩子/学科"
                >
                  ↗️
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(q.id) }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#ccc',
                    fontSize: '18px',
                    padding: '4px',
                    cursor: 'pointer',
                  }}
                  title="删除"
                >
                  ×
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
                  background: '#f8f9fa',
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
                  {Object.entries(children).map(([key, child]) => (
                    <option key={key} value={key}>{child.emoji} {child.name}</option>
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
                  {(children[moveChild]?.subjects || []).map(s => (
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
