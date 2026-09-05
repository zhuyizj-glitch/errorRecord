/** 复习重做页面 */

import { useEffect, useState } from 'react'
import { useStore } from '../store/useStore'
import { fetchReviewPlan } from '../api/client'
import type { Question } from '../types'

export default function ReviewPage() {
  const { currentChild } = useStore()
  const [plan, setPlan] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [submitting, setSubmitting] = useState(false)

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
        `/api/questions/${q.id}/redo?child=${currentChild}&subject=${encodeURIComponent(q.subject)}&result=${result}`,
        { method: 'POST' }
      ).then(r => r.json())

      if (res.success) {
        // 移到下一题
        if (currentIndex < plan.length - 1) {
          setCurrentIndex(currentIndex + 1)
          setShowAnswer(false)
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
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
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

        {/* 题目内容（从 body 中提取） */}
        <div style={{
          padding: '20px', background: '#f8f9fa',
          borderRadius: 'var(--radius-md)', marginBottom: '20px',
          fontSize: '16px', lineHeight: 1.8,
        }}>
          <p style={{ margin: 0, fontWeight: 500 }}>📄 题目</p>
          <p style={{ margin: '8px 0 0 0', color: 'var(--color-text)' }}>
            {/* 简单显示题目信息 */}
            知识点：{current.knowledge_points?.join('、') || current.topic}
          </p>
          <p style={{ margin: '8px 0 0 0', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            （点击查看完整题目和答案）
          </p>
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
            👀 查看答案
          </button>
        ) : (
          <div>
            <div style={{
              padding: '16px', background: '#e8f5e9',
              borderRadius: 'var(--radius-md)', marginBottom: '20px',
              border: '1px solid #a5d6a7',
            }}>
              <p style={{ margin: '0 0 4px 0', fontWeight: 600, color: 'var(--color-success)' }}>✅ 正确答案</p>
              <p style={{ margin: 0 }}>请回到错题列表查看该题的完整答案和解析。</p>
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
                ✅ 做对了
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
                ❌ 又错了
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
