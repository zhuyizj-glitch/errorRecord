/** 真题内容渲染（三形态统一）：independent / material_group / passage */

import { renderMarkdownWithMath } from '../../utils/mathRenderer'
import type { ZhentiQuestion } from '../../types'

const Math = ({ text }: { text?: string }) => (
  <div style={{ fontSize: 15, lineHeight: 1.85 }}
    dangerouslySetInnerHTML={{ __html: renderMarkdownWithMath(text || '') }} />
)

const answerBlock = {
  background: 'var(--color-surface-2)',
  border: '1px solid var(--color-success)',
  borderRadius: 'var(--radius-sm)',
  padding: '10px 14px',
  marginTop: 8,
} as React.CSSProperties

/** 渲染一道真题的题目与（可选）答案。revealed=false 时隐藏答案，供练习自评。 */
export default function ZhentiContent({ item, revealed }: { item: ZhentiQuestion; revealed: boolean }) {
  const form = item.question_form || 'independent'

  if (form === 'independent') {
    const q = item._question || item._body || ''
    return (
      <div>
        <Math text={q} />
        {item.has_diagram && item.diagram_description && (
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>图：{item.diagram_description}</p>
        )}
        {revealed && (
          <div style={answerBlock}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-success)', marginBottom: 4 }}>参考答案</div>
            <Math text={item._answer || '（无）'} />
            {item._solution && (
              <>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-text-secondary)', margin: '10px 0 4px' }}>解题分析</div>
                <Math text={item._solution} />
              </>
            )}
          </div>
        )}
      </div>
    )
  }

  // material_group / passage
  const subs = item.sub_questions || []
  return (
    <div>
      <div style={{
        background: 'var(--color-surface-2)', borderRadius: 'var(--radius-sm)',
        padding: '12px 16px', marginBottom: 14, borderLeft: '3px solid var(--color-primary)',
      }}>
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 6 }}>
          {form === 'passage' ? '语篇' : '共享材料'}
        </div>
        <Math text={item.passage || ''} />
        {item.has_diagram && item.diagram_description && (
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>图：{item.diagram_description}</p>
        )}
      </div>
      {subs.map((sub, i) => (
        <div key={i} style={{ marginBottom: 14, paddingBottom: 12, borderBottom: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: 'var(--color-text-secondary)' }}>
            第 {sub.number || i + 1} 题
            {sub.knowledge_points?.length > 0 && (
              <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', marginLeft: 8, fontSize: 12 }}>
                {sub.knowledge_points.join(' · ')}
              </span>
            )}
          </div>
          <Math text={sub.question_text} />
          {revealed && (
            <div style={answerBlock}>
              <Math text={sub.correct_answer || '（无）'} />
              {sub.solution_steps && <Math text={sub.solution_steps} />}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
