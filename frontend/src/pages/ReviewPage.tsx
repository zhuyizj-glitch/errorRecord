/** 复习重做页面 */

import { useEffect, useState } from 'react'
import { CircleCheck, CircleX, Eye, FileText, LoaderCircle, PencilLine, ScrollText, Search, type LucideIcon } from 'lucide-react'
import { useStore } from '../store/useStore'
import { fetchReviewPlan } from '../api/client'
import { renderMarkdownWithMath } from '../utils/mathRenderer'
import type { Question } from '../types'

export default function ReviewPage() {
  const { currentChild } = useStore()
  const [plan, setPlan] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  /** 做错原因（可选）。后端 RedoRequest.note 一直支持，只是前端从未提供输入框 */
  const [note, setNote] = useState('')
  const [showNoteBox, setShowNoteBox] = useState(false)

  useEffect(() => {
    if (!currentChild) return
    loadPlan()
  }, [currentChild])

  const loadPlan = async () => {
    if (!currentChild) return
    setLoading(true)
    try {
      const res = await fetchReviewPlan(currentChild)
      setPlan(res.plan || [])
      setCurrentIndex(0)
      setShowAnswer(false)
      setNote('')
      setShowNoteBox(false)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleRedo = async (result: 'correct' | 'wrong') => {
    if (!currentChild || !plan[currentIndex]) return
    const q = plan[currentIndex]
    setSubmitting(true)
    try {
      const res = await fetch(
        `/api/questions/${q.id}/redo?child_id=${currentChild}&subject=${encodeURIComponent(q.subject)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // note 可选：做错时家长填的原因，后端会追加进 redo_history
          body: JSON.stringify({ result, note: note.trim() || undefined }),
        }
      ).then(r => r.json())

      if (res.success) {
        // 移到下一题。错因输入也要一并重置 ——
        // 此前只重置了 showAnswer，结果上一题的错因会带到下一题。
        if (currentIndex < plan.length - 1) {
          setCurrentIndex(currentIndex + 1)
          setShowAnswer(false)
          setNote('')
          setShowNoteBox(false)
        } else {
          // 全部完成，刷新列表
          loadPlan()
        }
      }
    } catch (e) {
      console.error(e)
    } finally {
      setSubmitting(false)
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

  if (plan.length === 0) return (
    <div>
      <h2>📖 今日复习计划</h2>
      <div style={{
        textAlign: 'center', padding: '80px 20px',
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
      }}>
        <div style={{ fontSize: '64px', marginBottom: '16px' }}>🎉</div>
        <p style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-success)' }}>
          今天没有需要复习的错题！
        </p>
        <p style={{ color: 'var(--color-text-secondary)', marginTop: '8px' }}>
          去上传新错题，或者继续努力学习吧
        </p>
      </div>
    </div>
  )

  const current = plan[currentIndex]
  const progress = `${currentIndex + 1} / ${plan.length}`

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>📖 今日复习</h2>
        <span style={{
          padding: '6px 16px', borderRadius: '20px',
          background: 'var(--color-primary-light)',
          color: 'var(--color-primary)',
          fontSize: '14px', fontWeight: 600,
        }}>
          进度 {progress}
        </span>
      </div>

      {/* 进度条 */}
      <div style={{
        height: '4px', background: 'var(--color-border)',
        borderRadius: '2px', marginBottom: '24px', overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', background: 'var(--color-primary)',
          width: `${((currentIndex) / plan.length) * 100}%`,
          transition: 'width 0.3s',
        }} />
      </div>

      {/* 题目卡片 */}
      <div style={{
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        padding: '24px', border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
      }}>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          <span>{current.subject}</span>
          <span>·</span>
          <span>{current.topic}</span>
          <span>·</span>
          <span>掌握度 {current.mastery_score}分</span>
        </div>

        {/* 题目内容 —— 从正文里解析出来的题干（后端 _decorate 提供） */}
        <div style={{
          padding: '20px', background: 'var(--color-fill)',
          borderRadius: 'var(--radius-md)', marginBottom: '20px',
          fontSize: '16px', lineHeight: 1.9,
        }}>
          <p style={{
            margin: '0 0 10px 0', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
            fontSize: '13px', color: 'var(--color-text-secondary)',
          }}>
            <FileText size={16} />
            题目
          </p>
          <div
            style={{ color: 'var(--color-text)' }}
            dangerouslySetInnerHTML={{
              __html: renderMarkdownWithMath(
                current._structured === false
                  // 正文格式不是模板形状时，整段渲染，绝不显示空白
                  ? (current._body || '（这道题没有记录内容）')
                  : (current._question || '（这道题没有记录题干）')
              ),
            }}
          />
          {(current.knowledge_points?.length ?? 0) > 0 && (
            <p style={{ margin: '12px 0 0 0', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
              知识点：{current.knowledge_points!.join('、')}
            </p>
          )}
        </div>

        {/* 显示答案区域 */}
        {!showAnswer ? (
          <button
            onClick={() => setShowAnswer(true)}
            style={{
              width: '100%', padding: '14px',
              background: 'var(--color-primary)', color: '#fff',
              border: 'none', borderRadius: 'var(--radius-md)',
              fontSize: '16px', fontWeight: 600, cursor: 'pointer',
            }}
          >
            <Eye size={17} style={{ verticalAlign: '-3px', marginRight: 6 }} />
            查看答案
          </button>
        ) : (
          <div>
            {/* 答案区 —— 把后端解析出来的段落逐块渲染。
                此前这里是一句「请回到错题列表查看该题的完整答案和解析」，
                等于把答案藏起来了，复习页根本没法用。 */}
            {current._structured === false ? (
              <div style={{
                padding: '16px', background: 'var(--color-surface-2)',
                borderRadius: 'var(--radius-md)', marginBottom: '16px',
                lineHeight: 1.9,
              }}>
                <div dangerouslySetInnerHTML={{
                  __html: renderMarkdownWithMath(
                    current._body || '（这道题没有记录答案与解析）'
                  ),
                }} />
              </div>
            ) : (
              <>
                {current._answer && (
                  <AnswerBlock Icon={CircleCheck} title="正确答案" tone="success" text={current._answer} />
                )}
                {current._solution && (
                  <AnswerBlock Icon={ScrollText} title="解题过程" tone="plain" text={current._solution} />
                )}
                {current._error_analysis && (
                  <AnswerBlock Icon={Search} title="错误分析" tone="warning" text={current._error_analysis} />
                )}
                {!current._answer && !current._solution && !current._error_analysis && (
                  <p style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                    这道题只记录了题干，没有答案与解析。
                  </p>
                )}
              </>
            )}

            {/* 错因（可选）。做错时填一句，会进重做历史，便于看出反复出错的模式 */}
            <div style={{ marginBottom: '16px' }}>
              <button
                onClick={() => setShowNoteBox(v => !v)}
                style={{
                  background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                  color: 'var(--color-text-secondary)', fontSize: '13px',
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                }}
              >
                <PencilLine size={14} />
                {note ? '已填写错因' : showNoteBox ? '收起' : '记一下错因（可选）'}
              </button>
              {showNoteBox && (
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  placeholder="例如：把 ÷ 看成了 ×"
                  rows={2}
                  style={{
                    width: '100%', marginTop: '8px', padding: '10px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface-2)', color: 'var(--color-text)',
                    fontSize: '14px', fontFamily: 'inherit', resize: 'vertical',
                  }}
                />
              )}
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={() => handleRedo('correct')}
                disabled={submitting}
                style={{
                  flex: 1, padding: '14px',
                  background: 'var(--color-success)', color: '#fff',
                  border: 'none', borderRadius: 'var(--radius-md)',
                  fontSize: '16px', fontWeight: 600, cursor: 'pointer',
                }}
              >
                <CircleCheck size={17} style={{ verticalAlign: '-3px', marginRight: 6 }} />
                做对了
              </button>
              <button
                onClick={() => handleRedo('wrong')}
                disabled={submitting}
                style={{
                  flex: 1, padding: '14px',
                  background: 'var(--color-error)', color: '#fff',
                  border: 'none', borderRadius: 'var(--radius-md)',
                  fontSize: '16px', fontWeight: 600, cursor: 'pointer',
                }}
              >
                <CircleX size={17} style={{ verticalAlign: '-3px', marginRight: 6 }} />
                又错了
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** 答案区的一个段落块（正确答案 / 解题过程 / 错误分析） */
function AnswerBlock({
  Icon, title, tone, text,
}: {
  Icon: LucideIcon
  title: string
  tone: 'success' | 'warning' | 'plain'
  text: string
}) {
  const color = tone === 'success' ? 'var(--color-success)'
    : tone === 'warning' ? 'var(--color-warning)'
    : 'var(--color-text-secondary)'
  const background = tone === 'success' ? 'var(--color-success-light)'
    : tone === 'warning' ? 'var(--color-warning-light)'
    : 'var(--color-surface-2)'
  const border = tone === 'success' ? 'var(--color-success)'
    : tone === 'warning' ? 'var(--color-warning)'
    : 'var(--color-border)'

  return (
    <div style={{
      padding: '16px', background, borderRadius: 'var(--radius-md)',
      marginBottom: '16px', border: `1px solid ${border}`, lineHeight: 1.9,
    }}>
      <p style={{
        margin: '0 0 6px 0', fontWeight: 600, color, fontSize: '14px',
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <Icon size={16} />
        {title}
      </p>
      <div dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(text) }} />
    </div>
  )
}
