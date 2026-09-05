/** 错题详情页面 */

import { useEffect, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import type { Question } from '../types'
import { renderMarkdownWithMath } from '../utils/mathRenderer'

interface ImageInfo {
  filename: string
  url: string
}

export default function DetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const child = searchParams.get('child') || ''
  const subject = searchParams.get('subject') || ''

  const [question, setQuestion] = useState<Question | null>(null)
  const [body, setBody] = useState('')
  const [images, setImages] = useState<ImageInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id || !child || !subject) return

    Promise.all([
      fetch(`${import.meta.env.VITE_API_URL || ''}/api/questions/${id}?child=${child}&subject=${subject}`).then(r => r.json()),
      fetch(`${import.meta.env.VITE_API_URL || ''}/api/questions/${id}/images?child=${child}&subject=${subject}`).then(r => r.json()),
    ])
      .then(([qData, imgData]) => {
        const { _body, _file, ...rest } = qData
        setQuestion(rest as Question)
        setBody(_body || '')
        setImages(imgData.images || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id, child, subject])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--color-text-secondary)' }}>
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>⏳</div>
      加载中...
    </div>
  )

  if (!question) return (
    <div style={{ textAlign: 'center', padding: '60px' }}>
      <p>错题不存在</p>
      <button onClick={() => navigate('/list')} style={{ marginTop: '16px', padding: '8px 20px', cursor: 'pointer' }}>
        返回列表
      </button>
    </div>
  )

  const masteryColor = (level: string) => {
    switch (level) {
      case 'low': return '#d32f2f'
      case 'medium': return '#f57c00'
      case 'high': return '#2e7d32'
      default: return '#999'
    }
  }

  return (
    <div>
      <button
        onClick={() => navigate('/list')}
        style={{
          background: 'none', border: 'none', color: 'var(--color-primary)',
          fontSize: '14px', cursor: 'pointer', marginBottom: '16px', padding: 0,
        }}
      >
        ← 返回列表
      </button>

      {/* 头部信息 */}
      <div style={{
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        padding: '24px', border: '1px solid var(--color-border)', marginBottom: '20px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ margin: '0 0 8px 0', fontSize: '22px' }}>{question.topic}</h2>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '14px', color: 'var(--color-text-secondary)' }}>
              <span>{child === 'daughter' ? '👧 女儿' : '👦 儿子'} · {subject}</span>
              <span>📅 {question.error_date}</span>
              {question.error_type && <span>🏷 {question.error_type}</span>}
              <span>📊 {question.difficulty}</span>
            </div>
          </div>
          <div style={{
            padding: '12px 20px', borderRadius: 'var(--radius-md)',
            background: masteryColor(question.mastery_level) + '15',
            border: `1px solid ${masteryColor(question.mastery_level)}30`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '28px', fontWeight: 800, color: masteryColor(question.mastery_level) }}>
              {question.mastery_score}
            </div>
            <div style={{ fontSize: '12px', color: masteryColor(question.mastery_level) }}>
              掌握度
            </div>
          </div>
        </div>

        {/* 统计信息 */}
        <div style={{
          marginTop: '16px', paddingTop: '16px',
          borderTop: '1px solid var(--color-border)',
          display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '13px',
        }}>
          <span>🔄 重做 <strong>{question.redo_count}</strong> 次</span>
          <span>📅 下次复习 <strong>{question.next_review_date || '未安排'}</strong></span>
          {question.repeat_pattern && (
            <span style={{ color: 'var(--color-error)' }}>⚠️ 重复犯错模式（连续 {question.repeat_streak} 次）</span>
          )}
        </div>
      </div>

      {/* 图片 */}
      {images.length > 0 && (
        <div style={{
          background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
          padding: '20px', border: '1px solid var(--color-border)', marginBottom: '20px',
        }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>📷 题目图片</h3>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {images.map(img => (
              <img
                key={img.filename}
                src={img.url}
                alt={img.filename}
                style={{
                  maxWidth: '300px', maxHeight: '300px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  cursor: 'pointer',
                }}
                onClick={() => window.open(img.url, '_blank')}
              />
            ))}
          </div>
        </div>
      )}

      {/* 正文内容 */}
      <div style={{
        background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
        padding: '24px', border: '1px solid var(--color-border)', marginBottom: '20px',
        lineHeight: 1.8, fontSize: '15px',
      }}>
        <div dangerouslySetInnerHTML={{ __html: renderMarkdown(body) }} />
      </div>

      {/* 知识点标签 */}
      {question.knowledge_points?.length > 0 && (
        <div style={{
          background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
          padding: '20px', border: '1px solid var(--color-border)',
        }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>📚 知识点</h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {question.knowledge_points.map((kp, i) => (
              <span key={i} style={{
                padding: '4px 12px', borderRadius: '20px',
                background: 'var(--color-primary-light)',
                color: 'var(--color-primary)',
                fontSize: '13px',
              }}>
                {kp}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 重做历史 */}
      {question.redo_history && question.redo_history.length > 0 && (
        <div style={{
          background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)',
          padding: '20px', border: '1px solid var(--color-border)', marginTop: '20px',
        }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>📝 重做记录</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {question.redo_history && question.redo_history.map((r: any, i: number) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                background: r.result === 'correct' ? '#e8f5e9' : '#fff3f3',
              }}>
                <span>{r.result === 'correct' ? '✅' : '❌'}</span>
                <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>{r.date}</span>
                {r.note && <span style={{ fontSize: '13px' }}>{r.note}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// 使用带数学公式的 markdown 渲染
const renderMarkdown = renderMarkdownWithMath
