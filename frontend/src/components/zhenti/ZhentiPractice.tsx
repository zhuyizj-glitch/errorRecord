/** 针对性练习（三形态）：薄弱点推荐 + 时代/主题专项 + 语篇梯度 + 子题转错题 */

import { useCallback, useEffect, useState } from 'react'
import { Target, Eye, CheckCircle2, XCircle, ArrowRight, BookPlus, AlertTriangle } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { fetchZhentiRecommend, fetchZhentiDimensions, practiceZhenti, zhentiToMistake, fetchZhentiDetail } from '../../api/client'
import ZhentiContent from './ZhentiContent'
import type { WeakPoint, ZhentiRecommendation, ZhentiDimensions } from '../../types'

const chipStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 12px',
  borderRadius: 'var(--radius-full)', background: 'var(--color-primary-light)',
  color: 'var(--color-primary)', fontSize: 12, marginRight: 6, marginBottom: 6,
}
const btnPrimary: React.CSSProperties = {
  padding: '10px 20px', fontSize: 14, fontWeight: 600, background: 'var(--color-primary)',
  color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', gap: 6,
}
const selectStyle: React.CSSProperties = {
  background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
  borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', padding: '7px 10px', fontSize: 13,
}

export default function ZhentiPractice() {
  const currentChild = useStore(s => s.currentChild)
  const children = useStore(s => s.children)
  const child = children.find(c => c.id === currentChild)

  const [subject, setSubject] = useState('')
  const [era, setEra] = useState('')
  const [module, setModule] = useState('')
  const [dims, setDims] = useState<ZhentiDimensions>({ eras: [], modules: [], question_types: [], ratings: [] })
  const [weak, setWeak] = useState<WeakPoint[]>([])
  const [unmatched, setUnmatched] = useState<string[]>([])
  const [recs, setRecs] = useState<ZhentiRecommendation[]>([])
  const [passages, setPassages] = useState<ZhentiRecommendation[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [active, setActive] = useState<ZhentiRecommendation | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [graded, setGraded] = useState<'correct' | 'wrong' | null>(null)
  const [converted, setConverted] = useState<string[]>([])
  const [session, setSession] = useState({ done: 0, correct: 0 })

  useEffect(() => {
    fetchZhentiDimensions(subject || undefined).then(setDims).catch(() => {})
    setEra(''); setModule('')
  }, [subject])

  const load = useCallback(async () => {
    if (!currentChild) return
    setLoading(true); setMessage('')
    try {
      const res = await fetchZhentiRecommend(currentChild, subject || undefined,
        { era: era || undefined, module: module || undefined })
      setWeak(res.weak_points); setUnmatched(res.unmatched_points)
      setRecs(res.recommendations); setPassages(res.passages || [])
    } catch (e: any) { setMessage(e?.response?.data?.detail || '加载推荐失败') }
    finally { setLoading(false) }
  }, [currentChild, subject, era, module])

  useEffect(() => { load() }, [load])

  const startPractice = async (item: ZhentiRecommendation) => {
    try {
      const full = await fetchZhentiDetail(item.id)
      setActive({ ...item, ...full }); setRevealed(false); setGraded(null); setConverted([])
    } catch { setMessage('加载题目失败') }
  }

  const handleGrade = async (result: 'correct' | 'wrong') => {
    if (!active || !currentChild) return
    try {
      await practiceZhenti(active.id, { child_id: currentChild, result })
      setGraded(result)
      setSession(s => ({ done: s.done + 1, correct: s.correct + (result === 'correct' ? 1 : 0) }))
    } catch (e: any) { setMessage(e?.response?.data?.detail || '提交失败') }
  }

  const handleConvert = async (subNumber?: string) => {
    if (!active || !currentChild) return
    try {
      const res = await zhentiToMistake(active.id, { child_id: currentChild, sub_number: subNumber })
      setConverted(prev => [...prev, subNumber || 'whole'])
      setMessage(`已转为 ${res.child_name} 的错题，进入复习计划`)
    } catch (e: any) { setMessage(e?.response?.data?.detail || '转化失败') }
  }

  const handleNext = () => { setActive(null); setRecs(prev => prev.filter(r => r.id !== active?.id)) }

  if (!currentChild || !child) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-tertiary)' }}>
        <Target size={36} strokeWidth={1.5} />
        <p>请先在「孩子」页面创建孩子，练习推荐基于孩子的错题薄弱点</p>
      </div>
    )
  }

  if (active) {
    const matchedSubs = active.matched_sub_numbers || []
    return (
      <div style={{ maxWidth: 780, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
            {active.source}（{active.year}）第 {active.number || '?'} 题 · {active.subject}
            {active.question_type && ` · ${active.question_type}`}{active.rating && ` · ${active.rating}`}
          </span>
          <button onClick={handleNext} style={{ background: 'none', border: 'none', color: 'var(--color-text-tertiary)', cursor: 'pointer', fontSize: 13 }}>跳过 →</button>
        </div>
        {active.matched_points?.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            {active.matched_points.map(k => (
              <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>
                <Target size={11} /> 针对薄弱点：{k}
              </span>
            ))}
          </div>
        )}
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 20, marginBottom: 14 }}>
          <ZhentiContent item={active} revealed={revealed} />
        </div>

        {!revealed ? (
          <div style={{ textAlign: 'center', padding: '12px 0' }}>
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', marginBottom: 12 }}>在纸上完成作答后，再显示答案对照</p>
            <button onClick={() => setRevealed(true)} style={btnPrimary}><Eye size={15} /> 显示答案</button>
          </div>
        ) : !graded ? (
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', padding: '8px 0' }}>
            <button onClick={() => handleGrade('correct')} style={{ ...btnPrimary, background: 'var(--color-success)' }}><CheckCircle2 size={15} /> 做对了</button>
            <button onClick={() => handleGrade('wrong')} style={{ ...btnPrimary, background: 'var(--color-error)' }}><XCircle size={15} /> 还是错</button>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            {graded === 'wrong' && (
              <div style={{ marginBottom: 12 }}>
                <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 8 }}>转为错题后自动进入复习计划</p>
                {matchedSubs.length > 0 ? (
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                    {matchedSubs.map(sn => (
                      <button key={sn} disabled={converted.includes(sn)} onClick={() => handleConvert(sn)}
                        style={{ ...btnPrimary, background: converted.includes(sn) ? 'var(--color-fill)' : 'var(--color-warning)' }}>
                        <BookPlus size={15} /> {converted.includes(sn) ? `第${sn}题已转` : `第${sn}题转错题`}
                      </button>
                    ))}
                  </div>
                ) : (
                  <button disabled={converted.includes('whole')} onClick={() => handleConvert()}
                    style={{ ...btnPrimary, background: converted.includes('whole') ? 'var(--color-fill)' : 'var(--color-warning)' }}>
                    <BookPlus size={15} /> {converted.includes('whole') ? '已转为错题' : `转为${child.name}的错题`}
                  </button>
                )}
              </div>
            )}
            <button onClick={handleNext} style={btnPrimary}>下一题 <ArrowRight size={15} /></button>
          </div>
        )}
        {message && <p className="form-error" style={{ marginTop: 10, textAlign: 'center' }}>{message}</p>}
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          为 <strong style={{ color: 'var(--color-text)' }}>{child.emoji} {child.name}</strong> 推荐
        </span>
        <select value={subject} onChange={e => setSubject(e.target.value)} style={selectStyle}>
          <option value="">全部学科</option>
          {child.subjects.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {dims.eras.length > 0 && (
          <select value={era} onChange={e => setEra(e.target.value)} style={selectStyle}>
            <option value="">全部时代</option>
            {dims.eras.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
        )}
        {dims.modules.length > 0 && (
          <select value={module} onChange={e => setModule(e.target.value)} style={selectStyle}>
            <option value="">全部主题</option>
            {dims.modules.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        {session.done > 0 && <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>本次已练 {session.done} · 对 {session.correct}</span>}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>{loading ? '加载中…' : ''}</span>
      </div>
      {message && <p className="form-error" style={{ marginBottom: 10 }}>{message}</p>}

      {weak.length > 0 && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 10px', fontSize: 15 }}>
            <Target size={15} style={{ verticalAlign: '-3px', marginRight: 6, color: 'var(--color-warning)' }} />薄弱知识点排行
          </h3>
          <div>
            {weak.slice(0, 12).map(w => (
              <span key={w.knowledge_point} style={chipStyle} title={`薄弱度 ${w.weight} · ${w.question_count} 道错题`}>
                {w.knowledge_point}<strong style={{ opacity: 0.8 }}>×{w.question_count}</strong>
              </span>
            ))}
          </div>
          {unmatched.length > 0 && (
            <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--color-warning)', display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              <AlertTriangle size={13} /> 暂无匹配真题，建议导入：
              {unmatched.map(k => <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)', margin: '0 0 0 4px' }}>{k}</span>)}
            </p>
          )}
        </div>
      )}

      {weak.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 15 }}>🎉 这个孩子目前没有未掌握的错题</p>
        </div>
      )}

      {recs.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 15, margin: '0 0 10px' }}>知识点匹配推荐（{recs.length}）</h3>
          {recs.map(item => (
            <div key={item.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 4 }}>
                  {item.source}（{item.year}）第 {item.number || '?'} 题 · {item.subject}
                  {item.child_practice_count > 0 && ` · 已练 ${item.child_practice_count} 次`}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{item.topic || item.question_type || '未分类'}</div>
                <div>
                  {item.matched_points.map(k => (
                    <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}><Target size={11} /> {k}</span>
                  ))}
                  {item.matched_sub_numbers?.length ? (
                    <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>命中子题：{item.matched_sub_numbers.join('、')}</span>
                  ) : null}
                </div>
              </div>
              <button onClick={() => startPractice(item)} style={{ ...btnPrimary, whiteSpace: 'nowrap' }}>开始练习</button>
            </div>
          ))}
        </div>
      )}

      {passages.length > 0 && (
        <div>
          <h3 style={{ fontSize: 15, margin: '0 0 10px' }}>语篇整题·难度梯度（{passages.length}）</h3>
          {passages.map(item => (
            <div key={item.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 4 }}>
                  {item.source}（{item.year}）· {item.question_type} · {item.sub_questions?.length || 0} 子题
                </div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  <span style={{ color: item.rating === '简单' ? 'var(--color-success)' : item.rating === '较难' ? 'var(--color-error)' : 'var(--color-warning)' }}>●</span>
                  {' '}{item.rating || '中等'} · {item.topic || item.question_type}
                </div>
              </div>
              <button onClick={() => startPractice(item)} style={{ ...btnPrimary, whiteSpace: 'nowrap' }}>整篇练习</button>
            </div>
          ))}
        </div>
      )}

      {weak.length > 0 && recs.length === 0 && passages.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 14 }}>题库里还没有匹配的真题，到「导入」上传对应真题卷</p>
        </div>
      )}
    </div>
  )
}
