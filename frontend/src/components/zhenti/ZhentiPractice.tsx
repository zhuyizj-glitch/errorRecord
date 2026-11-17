/** 针对性练习（v2.0）：薄弱点排行 → 推荐真题 → 出题/自评 → 做错转错题 */

import { useCallback, useEffect, useState } from 'react'
import { Target, Eye, CheckCircle2, XCircle, ArrowRight, BookPlus, AlertTriangle } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { fetchZhentiRecommend, practiceZhenti, zhentiToMistake, fetchZhentiDetail } from '../../api/client'
import { renderMarkdownWithMath } from '../../utils/mathRenderer'
import type { WeakPoint, ZhentiRecommendation } from '../../types'

const chipStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '3px 12px', borderRadius: 'var(--radius-full)',
  background: 'var(--color-primary-light)', color: 'var(--color-primary)',
  fontSize: 12, marginRight: 6, marginBottom: 6,
}

const btnPrimary: React.CSSProperties = {
  padding: '10px 20px', fontSize: 14, fontWeight: 600,
  background: 'var(--color-primary)', color: '#fff', border: 'none',
  borderRadius: 'var(--radius-sm)', cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', gap: 6,
}

export default function ZhentiPractice() {
  const currentChild = useStore(s => s.currentChild)
  const children = useStore(s => s.children)
  const child = children.find(c => c.id === currentChild)

  const [subject, setSubject] = useState('')
  const [weak, setWeak] = useState<WeakPoint[]>([])
  const [unmatched, setUnmatched] = useState<string[]>([])
  const [recs, setRecs] = useState<ZhentiRecommendation[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  // 练习状态
  const [active, setActive] = useState<ZhentiRecommendation | null>(null)
  const [revealed, setRevealed] = useState(false)
  const [graded, setGraded] = useState<'correct' | 'wrong' | null>(null)
  const [converted, setConverted] = useState(false)
  const [session, setSession] = useState({ done: 0, correct: 0 })

  const load = useCallback(async () => {
    if (!currentChild) return
    setLoading(true)
    setMessage('')
    try {
      const res = await fetchZhentiRecommend(currentChild, subject || undefined)
      setWeak(res.weak_points)
      setUnmatched(res.unmatched_points)
      setRecs(res.recommendations)
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '加载推荐失败')
    } finally {
      setLoading(false)
    }
  }, [currentChild, subject])

  useEffect(() => { load() }, [load])

  const startPractice = async (item: ZhentiRecommendation) => {
    try {
      const full = await fetchZhentiDetail(item.id)
      setActive({ ...item, ...full })
      setRevealed(false)
      setGraded(null)
      setConverted(false)
    } catch {
      setMessage('加载题目失败')
    }
  }

  const handleGrade = async (result: 'correct' | 'wrong') => {
    if (!active || !currentChild) return
    try {
      await practiceZhenti(active.id, { child_id: currentChild, result })
      setGraded(result)
      setSession(s => ({ done: s.done + 1, correct: s.correct + (result === 'correct' ? 1 : 0) }))
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '提交失败')
    }
  }

  const handleConvert = async () => {
    if (!active || !currentChild) return
    try {
      const res = await zhentiToMistake(active.id, { child_id: currentChild })
      setConverted(true)
      setMessage(`已转为 ${res.child_name} 的错题，进入复习计划`)
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || '转化失败')
    }
  }

  const handleNext = () => {
    setActive(null)
    setRecs(prev => prev.filter(r => r.id !== active?.id))
  }

  if (!currentChild || !child) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-tertiary)' }}>
        <Target size={36} strokeWidth={1.5} />
        <p>请先在「孩子」页面创建孩子，练习推荐需要基于孩子的错题薄弱点</p>
      </div>
    )
  }

  // ── 练习进行中的视图 ──
  if (active) {
    return (
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
            {active.source}（{active.year}）第 {active.number || '?'} 题 · {active.subject}
          </span>
          <button onClick={handleNext} style={{ background: 'none', border: 'none', color: 'var(--color-text-tertiary)', cursor: 'pointer', fontSize: 13 }}>
            跳过 →
          </button>
        </div>
        <div style={{ marginBottom: 12 }}>
          {active.matched_points.map(k => (
            <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>
              <Target size={11} /> 针对薄弱点：{k}
            </span>
          ))}
        </div>

        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)', padding: 20, marginBottom: 14,
        }}>
          <div style={{ fontSize: 16, lineHeight: 1.9 }}
            dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(active._question || active._body || '') }} />
        </div>

        {!revealed ? (
          <div style={{ textAlign: 'center', padding: '12px 0' }}>
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', marginBottom: 12 }}>
              在纸上完成作答后，再显示答案对照
            </p>
            <button onClick={() => setRevealed(true)} style={btnPrimary}>
              <Eye size={15} /> 显示答案
            </button>
          </div>
        ) : (
          <div>
            <div style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-success)',
              borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 12,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-success)', marginBottom: 6 }}>参考答案</div>
              <div style={{ fontSize: 15, lineHeight: 1.8 }}
                dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(active._answer || '（无）') }} />
              {active._solution && (
                <>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-secondary)', margin: '12px 0 6px' }}>解题分析</div>
                  <div style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--color-text-secondary)' }}
                    dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(active._solution) }} />
                </>
              )}
            </div>

            {!graded ? (
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center', padding: '8px 0' }}>
                <button onClick={() => handleGrade('correct')} style={{ ...btnPrimary, background: 'var(--color-success)' }}>
                  <CheckCircle2 size={15} /> 做对了
                </button>
                <button onClick={() => handleGrade('wrong')} style={{ ...btnPrimary, background: 'var(--color-error)' }}>
                  <XCircle size={15} /> 还是错
                </button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                {graded === 'wrong' && !converted && (
                  <div style={{ marginBottom: 12 }}>
                    <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
                      这道题暴露的薄弱点值得跟进——转为错题后会自动进入复习计划
                    </p>
                    <button onClick={handleConvert} style={{ ...btnPrimary, background: 'var(--color-warning)' }}>
                      <BookPlus size={15} /> 转为{child.name}的错题
                    </button>
                  </div>
                )}
                {converted && (
                  <p style={{ fontSize: 13, color: 'var(--color-success)', marginBottom: 12 }}>
                    ✅ 已转为错题，复习页会按掌握度安排重做
                  </p>
                )}
                <button onClick={handleNext} style={btnPrimary}>
                  下一题 <ArrowRight size={15} />
                </button>
              </div>
            )}
          </div>
        )}
        {message && <p className="form-error" style={{ marginTop: 10, textAlign: 'center' }}>{message}</p>}
      </div>
    )
  }

  // ── 推荐总览视图 ──
  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 14, color: 'var(--color-text-secondary)' }}>
          为 <strong style={{ color: 'var(--color-text)' }}>{child.emoji} {child.name}</strong> 推荐
        </span>
        <select value={subject} onChange={e => setSubject(e.target.value)} style={{
          background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-sm)', color: 'var(--color-text)', padding: '7px 10px', fontSize: 13,
        }}>
          <option value="">全部学科</option>
          {child.subjects.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {session.done > 0 && (
          <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>
            本次已练 {session.done} 题 · 对 {session.correct}
          </span>
        )}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>{loading ? '加载中…' : ''}</span>
      </div>
      {message && <p className="form-error" style={{ marginBottom: 10 }}>{message}</p>}

      {weak.length > 0 && (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 16,
        }}>
          <h3 style={{ margin: '0 0 10px', fontSize: 15 }}>
            <Target size={15} style={{ verticalAlign: '-3px', marginRight: 6, color: 'var(--color-warning)' }} />
            薄弱知识点排行
          </h3>
          <div>
            {weak.slice(0, 12).map(w => (
              <span key={w.knowledge_point} style={chipStyle} title={`薄弱度 ${w.weight} · ${w.question_count} 道错题 · 平均掌握度 ${w.avg_mastery}`}>
                {w.knowledge_point}
                <strong style={{ opacity: 0.8 }}>×{w.question_count}</strong>
              </span>
            ))}
          </div>
          {unmatched.length > 0 && (
            <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--color-warning)', display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              <AlertTriangle size={13} />
              以下薄弱点暂无匹配真题，建议导入对应真题卷：
              {unmatched.map(k => <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)', margin: '0 0 0 4px' }}>{k}</span>)}
            </p>
          )}
        </div>
      )}

      {weak.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 15 }}>🎉 这个孩子目前没有未掌握的错题</p>
          <p style={{ fontSize: 13 }}>录入错题后，这里会按薄弱点推荐针对性真题</p>
        </div>
      )}

      {recs.length > 0 && (
        <div>
          <h3 style={{ fontSize: 15, margin: '0 0 10px' }}>推荐真题（{recs.length}）</h3>
          {recs.map(item => (
            <div key={item.id} style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)', padding: 14, marginBottom: 10,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
            }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 4 }}>
                  {item.source}（{item.year}）第 {item.number || '?'} 题 · {item.subject} · {item.difficulty}
                  {item.child_practice_count > 0 && <span style={{ marginLeft: 8 }}>已练 {item.child_practice_count} 次</span>}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{item.topic || '未分类'}</div>
                <div>
                  {item.matched_points.map(k => (
                    <span key={k} style={{ ...chipStyle, background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>
                      <Target size={11} /> {k}
                    </span>
                  ))}
                </div>
              </div>
              <button onClick={() => startPractice(item)} style={{ ...btnPrimary, whiteSpace: 'nowrap' }}>
                开始练习
              </button>
            </div>
          ))}
        </div>
      )}

      {weak.length > 0 && recs.length === 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--color-text-tertiary)' }}>
          <p style={{ fontSize: 14 }}>题库里还没有匹配这些薄弱点的真题</p>
          <p style={{ fontSize: 13 }}>到「导入」标签页上传对应知识点的往年真题卷</p>
        </div>
      )}
    </div>
  )
}
