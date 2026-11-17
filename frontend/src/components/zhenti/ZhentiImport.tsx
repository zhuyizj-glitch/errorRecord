/** 真题导入（v2.0）：上传试卷图片/PDF → AI 拆题 → 人工预览勾选 → 批量入库 */

import { useEffect, useRef, useState } from 'react'
import { FileUp, Loader2, CheckCircle2, XCircle, Trash2, Save } from 'lucide-react'
import ImageUploader from '../ImageUploader'
import { useStore } from '../../store/useStore'
import { uploadImages, importZhenti, saveZhentiQuestions } from '../../api/client'
import { renderMarkdownWithMath } from '../../utils/mathRenderer'
import type { ZhentiTask, ZhentiAnalysisItem } from '../../types'

const cardStyle: React.CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-md)',
  padding: '16px',
  marginBottom: '12px',
}

const inputStyle: React.CSSProperties = {
  background: 'var(--color-surface-2)',
  border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--color-text)',
  padding: '8px 10px',
  fontSize: '14px',
  width: '100%',
}

export default function ZhentiImport() {
  const availableSubjects = useStore(s => s.availableSubjects)
  const currentSubject = useStore(s => s.currentSubject)

  const [files, setFiles] = useState<File[]>([])
  const [subject, setSubject] = useState(currentSubject || '数学')
  const [year, setYear] = useState('')
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [tasks, setTasks] = useState<ZhentiTask[]>([])
  const [previews, setPreviews] = useState<Record<string, ZhentiAnalysisItem[]>>({})
  const [checked, setChecked] = useState<Record<string, boolean[]>>({})
  const [saved, setSaved] = useState<Record<string, number>>({})

  const tasksRef = useRef(tasks)
  tasksRef.current = tasks
  const previewsRef = useRef(previews)
  previewsRef.current = previews

  // 轮询进行中的任务（与错题上传页同一模式）
  useEffect(() => {
    const poll = async () => {
      const active = tasksRef.current.filter(t => t.status === 'pending' || t.status === 'processing')
      if (active.length === 0) return
      for (const task of active) {
        try {
          const res = await fetch(`/api/tasks/${task.id}`, { credentials: 'include' })
          if (!res.ok) continue
          const fresh: ZhentiTask = await res.json()
          setTasks(prev => prev.map(t => t.id === fresh.id ? fresh : t))
          if (fresh.status === 'completed' && fresh.result && !previewsRef.current[fresh.id]) {
            const items = fresh.result.questions.map(q => ({ ...q }))
            setPreviews(prev => ({ ...prev, [fresh.id]: items }))
            setChecked(prev => ({ ...prev, [fresh.id]: items.map(() => true) }))
          }
        } catch { /* 网络抖动忽略，下轮再试 */ }
      }
    }
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleStart = async () => {
    setMessage('')
    if (files.length === 0) { setMessage('请先选择试卷图片或 PDF'); return }
    if (!year.trim()) { setMessage('请填写真题年份，如 2024'); return }
    if (!source.trim()) { setMessage('请填写试卷来源，如「2024年中考数学卷」'); return }
    setBusy(true)
    try {
      const uploaded = await uploadImages(files)
      if (uploaded.warnings?.length) setMessage(uploaded.warnings.join('；'))
      const stubs: ZhentiTask[] = []
      for (const img of uploaded.image_ids) {
        const res = await importZhenti({ subject, year: year.trim(), source: source.trim(), image_ids: [img] })
        stubs.push({
          id: res.task_id, account_id: '', child_id: '', subject,
          image_ids: [img], kind: 'zhenti',
          meta: { year: year.trim(), source: source.trim() },
          status: 'pending', created_at: res.created_at,
        })
      }
      setTasks(prev => [...stubs, ...prev])
      setFiles([])
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '导入失败，请重试')
    } finally {
      setBusy(false)
    }
  }

  const updateItem = (taskId: string, index: number, patch: Partial<ZhentiAnalysisItem>) => {
    setPreviews(prev => ({
      ...prev,
      [taskId]: prev[taskId].map((item, i) => i === index ? { ...item, ...patch } : item),
    }))
  }

  const handleSave = async (task: ZhentiTask) => {
    const items = (previews[task.id] || []).filter((_, i) => checked[task.id]?.[i])
    if (items.length === 0) { setMessage('请至少勾选一道题'); return }
    try {
      const res = await saveZhentiQuestions({
        subject: task.subject, year: task.meta.year || year, source: task.meta.source || source,
        questions: items,
      })
      setSaved(prev => ({ ...prev, [task.id]: res.saved }))
      setMessage(`已入库 ${res.saved} 道真题`)
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '入库失败，请重试')
    }
  }

  const handleDeleteTask = async (taskId: string) => {
    fetch(`/api/tasks/${taskId}`, { method: 'DELETE', credentials: 'include' }).catch(() => {})
    setTasks(prev => prev.filter(t => t.id !== taskId))
  }

  return (
    <div>
      <div style={cardStyle}>
        <h3 style={{ margin: '0 0 12px', fontSize: '16px' }}>
          <FileUp size={16} style={{ verticalAlign: '-3px', marginRight: 6 }} />
          导入真题卷
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '10px', marginBottom: '12px' }}>
          <label style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            学科
            <select value={subject} onChange={e => setSubject(e.target.value)} style={{ ...inputStyle, marginTop: 4 }}>
              {(availableSubjects.length ? availableSubjects : ['数学']).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            年份
            <input value={year} onChange={e => setYear(e.target.value)} placeholder="如 2024" style={{ ...inputStyle, marginTop: 4 }} />
          </label>
          <label style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            试卷来源
            <input value={source} onChange={e => setSource(e.target.value)} placeholder="如 2024年中考数学卷" style={{ ...inputStyle, marginTop: 4 }} />
          </label>
        </div>
        <ImageUploader files={files} setFiles={setFiles} allowPdf />
        <button
          onClick={handleStart}
          disabled={busy}
          style={{
            marginTop: 14, padding: '10px 22px', fontSize: '15px', fontWeight: 600,
            background: 'var(--color-primary)', color: '#fff', border: 'none',
            borderRadius: 'var(--radius-sm)', cursor: busy ? 'wait' : 'pointer',
          }}
        >
          {busy ? '上传中…' : '📷 开始识别真题'}
        </button>
        <p style={{ margin: '8px 0 0', fontSize: '12px', color: 'var(--color-text-tertiary)' }}>
          每页试卷一个任务，识别完成后可逐题核对、修改知识点，勾选后入库。PDF 会自动逐页拆分。
        </p>
        {message && <p className="form-error" style={{ marginTop: 8 }}>{message}</p>}
      </div>

      {tasks.length > 0 && (
        <div>
          <h3 style={{ fontSize: '16px', margin: '20px 0 10px' }}>识别任务（{tasks.length}）</h3>
          {tasks.map(task => (
            <div key={task.id} style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                  {task.meta.source}（{task.meta.year}）· {task.subject} · {task.image_ids[0]?.filename || '试卷页'}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {task.status === 'pending' || task.status === 'processing' ? (
                    <span style={{ color: 'var(--color-warning)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Loader2 size={14} className="spin" /> 识别中…
                    </span>
                  ) : task.status === 'completed' ? (
                    <span style={{ color: 'var(--color-success)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <CheckCircle2 size={14} /> 完成
                    </span>
                  ) : (
                    <span style={{ color: 'var(--color-error)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <XCircle size={14} /> 失败
                    </span>
                  )}
                  <button onClick={() => handleDeleteTask(task.id)} title="删除任务"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', padding: 2 }}>
                    <Trash2 size={14} />
                  </button>
                </span>
              </div>

              {task.status === 'failed' && (
                <p style={{ color: 'var(--color-error)', fontSize: 13, margin: '4px 0' }}>{task.error}</p>
              )}

              {task.status === 'completed' && previews[task.id] && (
                saved[task.id] !== undefined ? (
                  <p style={{ color: 'var(--color-success)', fontSize: 14, margin: '4px 0' }}>
                    ✅ 已入库 {saved[task.id]} 道真题，可到「题库」查看
                  </p>
                ) : (
                  <div>
                    {previews[task.id].map((item, i) => (
                      <div key={i} style={{
                        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)',
                        padding: '10px 12px', marginBottom: 8, background: 'var(--color-surface-2)',
                        opacity: checked[task.id]?.[i] ? 1 : 0.5,
                      }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                          <input type="checkbox" checked={checked[task.id]?.[i] ?? true}
                            onChange={e => setChecked(prev => ({
                              ...prev,
                              [task.id]: prev[task.id].map((v, j) => j === i ? e.target.checked : v),
                            }))}
                            style={{ marginTop: 4 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                              第 {item.number || '?'} 题 · {item.topic || '未分类'}
                              <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', marginLeft: 8 }}>{item.difficulty}</span>
                            </div>
                            <div style={{ fontSize: 14, lineHeight: 1.7 }}
                              dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(item.question_text) }} />
                            <details style={{ marginTop: 6 }}>
                              <summary style={{ fontSize: 13, color: 'var(--color-text-secondary)', cursor: 'pointer' }}>参考答案与解析</summary>
                              <div style={{ fontSize: 13, lineHeight: 1.7, marginTop: 4 }}
                                dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(item.correct_answer) }} />
                              {item.solution_steps && (
                                <div style={{ fontSize: 13, lineHeight: 1.7, marginTop: 4, color: 'var(--color-text-secondary)' }}
                                  dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(item.solution_steps) }} />
                              )}
                            </details>
                            <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
                              <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>知识点</span>
                              <input
                                value={item.knowledge_points.join('，')}
                                onChange={e => updateItem(task.id, i, {
                                  knowledge_points: e.target.value.split(/[,，、]/).map(s => s.trim()).filter(Boolean),
                                })}
                                placeholder="用逗号分隔，尽量与错题标签一致"
                                style={{ ...inputStyle, fontSize: 13, padding: '5px 8px' }}
                              />
                              <select value={item.difficulty}
                                onChange={e => updateItem(task.id, i, { difficulty: e.target.value })}
                                style={{ ...inputStyle, width: 80, fontSize: 13, padding: '5px 6px' }}>
                                <option>简单</option><option>中等</option><option>较难</option>
                              </select>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    <button onClick={() => handleSave(task)} style={{
                      padding: '8px 18px', fontSize: 14, fontWeight: 600,
                      background: 'var(--color-success)', color: '#fff', border: 'none',
                      borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 6,
                    }}>
                      <Save size={14} /> 保存勾选的真题（{(checked[task.id] || []).filter(Boolean).length} 道）
                    </button>
                  </div>
                )
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
