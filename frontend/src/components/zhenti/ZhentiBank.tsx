/** 真题库浏览（v2.0）：筛选、详情、编辑标签、删除 */

import { useCallback, useEffect, useState } from 'react'
import { Search, Trash2, Pencil, X } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { fetchZhentiQuestions, fetchZhentiDetail, patchZhenti, deleteZhenti } from '../../api/client'
import { renderMarkdownWithMath } from '../../utils/mathRenderer'
import type { ZhentiQuestion } from '../../types'

const inputStyle: React.CSSProperties = {
  background: 'var(--color-surface-2)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--color-text)',
  padding: '8px 10px',
  fontSize: '14px',
}

const chipStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '2px 10px',
  borderRadius: 'var(--radius-full)',
  background: 'var(--color-primary-light)',
  color: 'var(--color-primary)',
  fontSize: 12,
  marginRight: 6,
  marginBottom: 4,
}

export default function ZhentiBank() {
  const availableSubjects = useStore(s => s.availableSubjects)
  const [subject, setSubject] = useState('')
  const [year, setYear] = useState('')
  const [kp, setKp] = useState('')
  const [items, setItems] = useState<ZhentiQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<ZhentiQuestion | null>(null)
  const [editing, setEditing] = useState(false)
  const [editKps, setEditKps] = useState('')
  const [editYear, setEditYear] = useState('')
  const [editSource, setEditSource] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (subject) params.subject = subject
      if (year.trim()) params.year = year.trim()
      if (kp.trim()) params.knowledge_point = kp.trim()
      const res = await fetchZhentiQuestions(params)
      setItems(res.questions)
    } catch {
      setMessage('加载题库失败')
    } finally {
      setLoading(false)
    }
  }, [subject, year, kp])

  useEffect(() => { load() }, [load])

  const openDetail = async (item: ZhentiQuestion) => {
    try {
      const full = await fetchZhentiDetail(item.id)
      setDetail(full)
      setEditing(false)
      setEditKps((full.knowledge_points || []).join('，'))
      setEditYear(full.year || '')
      setEditSource(full.source || '')
    } catch {
      setMessage('加载详情失败')
    }
  }

  const handleSaveEdit = async () => {
    if (!detail) return
    try {
      await patchZhenti(detail.id, {
        knowledge_points: editKps.split(/[,，、]/).map(s => s.trim()).filter(Boolean),
        year: editYear.trim() || undefined,
        source: editSource.trim() || undefined,
      })
      setMessage('已保存修改')
      setEditing(false)
      setDetail(null)
      load()
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '保存失败')
    }
  }

  const handleDelete = async (item: ZhentiQuestion) => {
    if (!window.confirm(`确认删除这道真题？\n${item.source}（${item.year}）第 ${item.number || '?'} 题\n删除后不可恢复。`)) return
    try {
      await deleteZhenti(item.id)
      setDetail(null)
      load()
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '删除失败')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={subject} onChange={e => setSubject(e.target.value)} style={inputStyle}>
          <option value="">全部学科</option>
          {availableSubjects.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <input value={year} onChange={e => setYear(e.target.value)} placeholder="年份" style={{ ...inputStyle, width: 90 }} />
        <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: 'var(--color-text-tertiary)' }} />
          <input value={kp} onChange={e => setKp(e.target.value)} placeholder="按知识点搜索…" style={{ ...inputStyle, width: '100%', paddingLeft: 30 }} />
        </div>
        <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>
          {loading ? '加载中…' : `共 ${items.length} 道`}
        </span>
      </div>
      {message && <p className="form-error" style={{ marginBottom: 10 }}>{message}</p>}

      {items.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 15 }}>题库还是空的</p>
          <p style={{ fontSize: 13 }}>到「导入」标签页上传往年真题卷，AI 会自动拆题标注知识点</p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
        {items.map(item => (
          <div key={item.id} onClick={() => openDetail(item)} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)', padding: 14, cursor: 'pointer',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 6 }}>
              <span>{item.source}（{item.year}）</span>
              <span>{item.subject} · 第{item.number || '?'}题</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{item.topic || '未分类'}</div>
            <div style={{ marginBottom: 6 }}>
              {(item.knowledge_points || []).map(k => <span key={k} style={chipStyle}>{k}</span>)}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', display: 'flex', gap: 12 }}>
              <span>{item.difficulty}</span>
              <span>练 {item.practice_count} 次</span>
              {item.converted_to?.length ? <span>转错题 {item.converted_to.length}</span> : null}
            </div>
          </div>
        ))}
      </div>

      {detail && (
        <div onClick={() => setDetail(null)} style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 100,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
            maxWidth: 720, width: '100%', maxHeight: '85vh', overflow: 'auto', padding: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>
                {detail.source}（{detail.year}）第 {detail.number || '?'} 题
              </h3>
              <button onClick={() => setDetail(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)' }}>
                <X size={18} />
              </button>
            </div>

            {editing ? (
              <div style={{ display: 'grid', gap: 10, marginBottom: 12 }}>
                <label style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                  知识点（逗号分隔，与错题标签一致才能匹配推荐）
                  <input value={editKps} onChange={e => setEditKps(e.target.value)} style={{ ...inputStyle, width: '100%', marginTop: 4 }} />
                </label>
                <div style={{ display: 'flex', gap: 10 }}>
                  <label style={{ fontSize: 13, color: 'var(--color-text-secondary)', flex: 1 }}>
                    年份
                    <input value={editYear} onChange={e => setEditYear(e.target.value)} style={{ ...inputStyle, width: '100%', marginTop: 4 }} />
                  </label>
                  <label style={{ fontSize: 13, color: 'var(--color-text-secondary)', flex: 2 }}>
                    来源
                    <input value={editSource} onChange={e => setEditSource(e.target.value)} style={{ ...inputStyle, width: '100%', marginTop: 4 }} />
                  </label>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleSaveEdit} style={{ padding: '8px 16px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 14 }}>保存</button>
                  <button onClick={() => setEditing(false)} style={{ padding: '8px 16px', background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 14 }}>取消</button>
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: 12 }}>
                {(detail.knowledge_points || []).map(k => <span key={k} style={chipStyle}>{k}</span>)}
                <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginLeft: 8 }}>{detail.difficulty} · {detail.topic}</span>
              </div>
            )}

            <div style={{ fontSize: 15, lineHeight: 1.8, marginBottom: 14 }}
              dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(detail._question || detail._body || '') }} />
            <details open style={{ marginBottom: 10 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: 14, color: 'var(--color-success)' }}>参考答案</summary>
              <div style={{ fontSize: 14, lineHeight: 1.8, marginTop: 6 }}
                dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(detail._answer || '（无）') }} />
            </details>
            {detail._solution && (
              <details style={{ marginBottom: 14 }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600, fontSize: 14, color: 'var(--color-text-secondary)' }}>解题分析</summary>
                <div style={{ fontSize: 14, lineHeight: 1.8, marginTop: 6 }}
                  dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(detail._solution) }} />
              </details>
            )}

            <div style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--color-border)', paddingTop: 12 }}>
              {!editing && (
                <button onClick={() => setEditing(true)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '7px 14px', background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>
                  <Pencil size={13} /> 编辑标签
                </button>
              )}
              <button onClick={() => handleDelete(detail)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '7px 14px', background: 'var(--color-error-light)', color: 'var(--color-error)', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>
                <Trash2 size={13} /> 删除
              </button>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', alignSelf: 'center' }}>
                练习 {detail.practice_count} 次 · 对 {detail.correct_count} / 错 {detail.wrong_count}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
