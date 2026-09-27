import { FormEvent, useState } from 'react'
import { createChild, updateChild } from '../api/client'
import { useStore } from '../store/useStore'
import type { Child } from '../types'

const EMPTY = { name: '', emoji: '🧒', subjects: [] as string[] }
export default function ChildrenPage() {
  const { children, availableSubjects, fetchChildren } = useStore(); const [editing, setEditing] = useState<string | null>(null); const [form, setForm] = useState(EMPTY); const [error, setError] = useState('')
  const edit = (child: Child) => { setEditing(child.id); setForm({ name: child.name, emoji: child.emoji, subjects: child.subjects }) }
  const submit = async (e: FormEvent) => { e.preventDefault(); setError(''); try { editing ? await updateChild(editing, form) : await createChild(form); await fetchChildren(); setEditing(null); setForm(EMPTY) } catch (err: any) { setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || '保存失败') } }
  const toggle = (subject: string) => setForm({ ...form, subjects: form.subjects.includes(subject) ? form.subjects.filter(s => s !== subject) : [...form.subjects, subject] })
  return <div><h2>👶 孩子与课程</h2><div className="two-column"><section className="panel"><h3>已创建的孩子</h3>{children.length === 0 && <p>还没有孩子，请先创建。</p>}{children.map(c => <button className="child-row" key={c.id} onClick={() => edit(c)}>{c.emoji} {c.name}<small>{c.subjects.join('、')}</small></button>)}</section>
    <form className="panel auth-form" onSubmit={submit}><h3>{editing ? '编辑孩子' : '新增孩子'}</h3><input required value={form.name} placeholder="姓名或称呼" onChange={e => setForm({ ...form, name: e.target.value })} /><input required value={form.emoji} placeholder="Emoji" onChange={e => setForm({ ...form, emoji: e.target.value })} /><div className="subject-grid">{availableSubjects.map(s => <label key={s}><input type="checkbox" checked={form.subjects.includes(s)} onChange={() => toggle(s)} /> {s}</label>)}</div>{error && <p className="form-error">{error}</p>}<button type="submit">保存</button>{editing && <button type="button" className="secondary" onClick={() => { setEditing(null); setForm(EMPTY) }}>取消编辑</button>}</form></div></div>
}
