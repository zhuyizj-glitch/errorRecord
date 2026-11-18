/** 真题库浏览（三形态）：筛选、详情、编辑、删除 */

import { useCallback, useEffect, useState } from 'react'
import { Search, Trash2, Pencil, X } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { fetchZhentiQuestions, fetchZhentiDetail, fetchZhentiDimensions, patchZhenti, deleteZhenti } from '../../api/client'
import ZhentiContent from './ZhentiContent'
import type { ZhentiQuestion, ZhentiDimensions } from '../../types'

const inputStyle: React.CSSProperties = {
  background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', padding: '8px 10px', fontSize: 14,
}
const chipStyle: React.CSSProperties = {
  display: 'inline-block', padding: '2px 10px', borderRadius: 'var(--radius-full)',
  background: 'var(--color-primary-light)', color: 'var(--color-primary)',
  fontSize: 12, marginRight: 6, marginBottom: 4,
}
const FORM_LABEL: Record<string, string> = {
  independent: '独立小题', material_group: '材料组题', passage: '语篇整题',
}

export default function ZhentiBank() {
  const availableSubjects = useStore(s => s.availableSubjects)
  const [subject, setSubject] = useState('')
  const [year, setYear] = useState('')
  const [kp, setKp] = useState('')
  const [era, setEra] = useState('')
  const [module, setModule] = useState('')
  const [qtype, setQtype] = useState('')
  const [stage, setStage] = useState('')
  const [dims, setDims] = useState<ZhentiDimensions>({ eras: [], modules: [], question_types: [], ratings: [], stages: [] })
  const [items, setItems] = useState<ZhentiQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<ZhentiQuestion | null>(null)
  const [editing, setEditing] = useState(false)
  const [editKps, setEditKps] = useState('')
  const [editRating, setEditRating] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetchZhentiDimensions(subject || undefined).then(setDims).catch(() => {})
    setEra(''); setModule(''); setQtype(''); setStage('')
  }, [subject])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (subject) params.subject = subject
      if (year.trim()) params.year = year.trim()
      if (kp.trim()) params.knowledge_point = kp.trim()
      if (era) params.era = era
      if (module) params.module = module
      if (qtype) params.question_type = qtype
      if (stage) params.stage = stage
      const res = await fetchZhentiQuestions(params)
      setItems(res.questions)
    } catch { setMessage('加载题库失败') } finally { setLoading(false) }
  }, [subject, year, kp, era, module, qtype, stage])

  useEffect(() => { load() }, [load])

  const openDetail = async (item: ZhentiQuestion) => {
    try {
      const full = await fetchZhentiDetail(item.id)
      setDetail(full); setEditing(false)
      setEditKps((full.knowledge_points || []).join('，'))
      setEditRating(full.rating || '')
    } catch { setMessage('加载详情失败') }
  }

  const handleSaveEdit = async () => {
    if (!detail) return
    try {
      await patchZhenti(detail.id, {
        knowledge_points: editKps.split(/[,，、]/).map(s => s.trim()).filter(Boolean),
        rating: editRating || undefined,
      })
      setMessage('已保存修改'); setEditing(false); setDetail(null); load()
    } catch (e: any) { setMessage(e?.response?.data?.detail || '保存失败') }
  }

  const handleDelete = async (item: ZhentiQuestion) => {
    if (!window.confirm(`确认删除这道真题？\n${item.source}（${item.year}）第 ${item.number || '?'} 题`)) return
    try { await deleteZhenti(item.id); setDetail(null); load() }
    catch (e: any) { setMessage(e?.response?.data?.detail || '删除失败') }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={subject} onChange={e => setSubject(e.target.value)} style={inputStyle}>
          <option value="">全部学科</option>
          {availableSubjects.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <input value={year} onChange={e => setYear(e.target.value)} placeholder="年份" style={{ ...inputStyle, width: 80 }} />
        {dims.eras.length > 0 && (
          <select value={era} onChange={e => setEra(e.target.value)} style={inputStyle}>
            <option value="">全部时代</option>
            {dims.eras.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
        )}
        {dims.modules.length > 0 && (
          <select value={module} onChange={e => setModule(e.target.value)} style={inputStyle}>
            <option value="">全部主题</option>
            {dims.modules.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        {dims.question_types.length > 0 && (
          <select value={qtype} onChange={e => setQtype(e.target.value)} style={inputStyle}>
            <option value="">全部题型</option>
            {dims.question_types.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        {dims.stages.length > 0 && (
          <select value={stage} onChange={e => setStage(e.target.value)} style={inputStyle}>
            <option value="">全部阶段</option>
            {dims.stages.map(st => <option key={st} value={st}>{st}</option>)}
          </select>
        )}
        <div style={{ position: 'relative', flex: 1, minWidth: 160 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: 'var(--color-text-tertiary)' }} />
          <input value={kp} onChange={e => setKp(e.target.value)} placeholder="按知识点搜索…" style={{ ...inputStyle, width: '100%', paddingLeft: 30 }} />
        </div>
        <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>{loading ? '加载中…' : `共 ${items.length} 道`}</span>
      </div>
      {message && <p className="form-error" style={{ marginBottom: 10 }}>{message}</p>}

      {items.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 15 }}>题库还是空的</p>
          <p style={{ fontSize: 13 }}>到「导入」标签页上传往年真题卷</p>
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
            <div style={{ fontSize: 13, marginBottom: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ ...chipStyle, background: 'var(--color-fill)', color: 'var(--color-text-secondary)' }}>
                {FORM_LABEL[item.question_form] || '独立小题'}
              </span>
              {item.question_type && <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{item.question_type}</span>}
              {item.rating && <span style={{ fontSize: 12, color: 'var(--color-warning)' }}>评级·{item.rating}</span>}
              {item.era && <span style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>{item.era}</span>}
              {item.module && <span style={{ ...chipStyle, background: 'var(--color-success-light)', color: 'var(--color-success)' }}>{item.module}</span>}
              {item.stage && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{item.stage}</span>}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{item.topic || item.question_type || '未分类'}</div>
            <div style={{ marginBottom: 6 }}>
              {(item.knowledge_points || []).slice(0, 4).map(k => <span key={k} style={chipStyle}>{k}</span>)}
              {item.question_form !== 'independent' && (
                <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{item.sub_questions?.length || 0} 个子题</span>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>练 {item.practice_count} 次</div>
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
            maxWidth: 760, width: '100%', maxHeight: '85vh', overflow: 'auto', padding: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>
                {detail.source}（{detail.year}）第 {detail.number || '?'} 题
                <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--color-text-tertiary)', marginLeft: 8 }}>
                  {FORM_LABEL[detail.question_form]} {detail.question_type} {detail.rating && `· ${detail.rating}`}
                </span>
              </h3>
              <button onClick={() => setDetail(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)' }}><X size={18} /></button>
            </div>

            {editing ? (
              <div style={{ display: 'grid', gap: 10, marginBottom: 14 }}>
                <label style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                  顶层知识点（逗号分隔）
                  <input value={editKps} onChange={e => setEditKps(e.target.value)} style={{ ...inputStyle, width: '100%', marginTop: 4 }} />
                </label>
                {detail.question_form === 'passage' && (
                  <label style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                    难度评级
                    <select value={editRating} onChange={e => setEditRating(e.target.value)} style={{ ...inputStyle, marginTop: 4 }}>
                      <option value="">未评</option><option>简单</option><option>中等</option><option>较难</option>
                    </select>
                  </label>
                )}
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleSaveEdit} style={{ padding: '8px 16px', background: 'var(--color-primary)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>保存</button>
                  <button onClick={() => setEditing(false)} style={{ padding: '8px 16px', background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}>取消</button>
                </div>
              </div>
            ) : (
              <div style={{ marginBottom: 12 }}>
                {detail.era && <span style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>时代·{detail.era}</span>}
                {detail.module && <span style={{ ...chipStyle, background: 'var(--color-success-light)', color: 'var(--color-success)' }}>主题·{detail.module}</span>}
                {(detail.knowledge_points || []).map(k => <span key={k} style={chipStyle}>{k}</span>)}
              </div>
            )}

            <ZhentiContent item={detail} revealed={true} />

            <div style={{ display: 'flex', gap: 8, borderTop: '1px solid var(--color-border)', paddingTop: 12, marginTop: 12 }}>
              {!editing && (
                <button onClick={() => setEditing(true)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '7px 14px', background: 'var(--color-surface-2)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>
                  <Pencil size={13} /> 编辑
                </button>
              )}
              <button onClick={() => handleDelete(detail)} style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '7px 14px', background: 'var(--color-error-light)', color: 'var(--color-error)', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>
                <Trash2 size={13} /> 删除
              </button>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', alignSelf: 'center' }}>
                练 {detail.practice_count} · 对 {detail.correct_count} / 错 {detail.wrong_count}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
