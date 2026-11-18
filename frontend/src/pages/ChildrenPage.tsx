import { FormEvent, useState } from 'react'
import { Baby } from 'lucide-react'
import { createChild, updateChild } from '../api/client'
import { useStore } from '../store/useStore'
import type { Child } from '../types'

const EMPTY = { name: '', emoji: '🧒', subjects: [] as string[], current_stage: '' }

export default function ChildrenPage() {
  const { children, availableSubjects, availableStages, fetchChildren } = useStore()
  const [editing, setEditing] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')

  const edit = (child: Child) => {
    setEditing(child.id)
    setForm({ name: child.name, emoji: child.emoji, subjects: child.subjects, current_stage: child.current_stage || '' })
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setError('')
    try {
      editing ? await updateChild(editing, form) : await createChild(form)
      await fetchChildren(); setEditing(null); setForm(EMPTY)
    } catch (err: any) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || '保存失败')
    }
  }
  const toggle = (subject: string) => setForm({
    ...form,
    subjects: form.subjects.includes(subject) ? form.subjects.filter(s => s !== subject) : [...form.subjects, subject],
  })

  return (
    <div>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Baby size={20} />孩子与课程</h2>
      <div className="two-column">
        <section className="panel">
          <h3>已创建的孩子</h3>
          {children.length === 0 && <p>还没有孩子，请先创建。</p>}
          {children.map(c => (
            <button className="child-row" key={c.id} onClick={() => edit(c)}>
              {c.emoji} {c.name}
              <small>{c.subjects.join('、')}{c.current_stage ? ` · ${c.current_stage}` : ''}</small>
            </button>
          ))}
        </section>
        <form className="panel auth-form" onSubmit={submit}>
          <h3>{editing ? '编辑孩子' : '新增孩子'}</h3>
          <input required value={form.name} placeholder="姓名或称呼" onChange={e => setForm({ ...form, name: e.target.value })} />
          <input required value={form.emoji} placeholder="Emoji" onChange={e => setForm({ ...form, emoji: e.target.value })} />
          <label style={{ fontSize: 13, color: 'var(--color-text-secondary)', display: 'block', margin: '8px 0 4px' }}>
            当前学习阶段（推荐真题时只推此阶段及之前的题，避免超纲）
          </label>
          <select value={form.current_stage} onChange={e => setForm({ ...form, current_stage: e.target.value })}
            style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', padding: '8px 10px', fontSize: 14, width: '100%' }}>
            <option value="">未设置（推荐不限阶段）</option>
            {availableStages.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <div className="subject-grid">
            {availableSubjects.map(s => (
              <label key={s}><input type="checkbox" checked={form.subjects.includes(s)} onChange={() => toggle(s)} /> {s}</label>
            ))}
          </div>
          {error && <p className="form-error">{error}</p>}
          <button type="submit">保存</button>
          {editing && <button type="button" className="secondary" onClick={() => { setEditing(null); setForm(EMPTY) }}>取消编辑</button>}
        </form>
      </div>
    </div>
  )
}
