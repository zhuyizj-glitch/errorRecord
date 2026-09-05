/** AI 分析结果预览组件 - 支持编辑 */

import type { AnalyzeResult } from '../types'
import { renderMathInText } from '../utils/mathRenderer'

interface Props {
  result: AnalyzeResult | null
  editable?: boolean
  onChange?: (result: AnalyzeResult) => void
}

export default function AnalysisPreview({ result, editable = false, onChange }: Props) {
  if (!result) return <p style={{ color: 'var(--color-text-secondary)' }}>暂无分析结果</p>

  const confidenceConfig: Record<string, { icon: string; color: string; label: string }> = {
    high: { icon: '🟢', color: '#2e7d32', label: '高' },
    medium: { icon: '🟡', color: '#f57c00', label: '中' },
    low: { icon: '🔴', color: '#d32f2f', label: '低' },
  }
  const conf = confidenceConfig[result.confidence] || confidenceConfig.medium

  const updateField = (field: string, value: any) => {
    if (onChange) {
      onChange({ ...result, [field]: value })
    }
  }

  const updateErrorAnalysis = (field: string, value: string) => {
    if (onChange && result.error_analysis) {
      onChange({
        ...result,
        error_analysis: { ...result.error_analysis, [field]: value }
      })
    }
  }

  const updateMetadata = (field: string, value: any) => {
    if (onChange) {
      onChange({
        ...result,
        metadata: { ...result.metadata, [field]: value }
      })
    }
  }

  return (
    <div>
      {/* 置信度 */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 12px',
        borderRadius: '20px',
        background: conf.color + '12',
        color: conf.color,
        fontSize: '13px',
        fontWeight: 500,
        marginBottom: '16px',
      }}>
        {conf.icon} AI 识别置信度：{conf.label}
        {result.confidence === 'low' && ' — 请仔细核对'}
      </div>

      {/* 题目 */}
      <Section title="📄 题目内容">
        {editable ? (
          <textarea
            value={result.question_text || ''}
            onChange={e => updateField('question_text', e.target.value)}
            style={{
              width: '100%',
              minHeight: '60px',
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontSize: '14px',
              lineHeight: 1.7,
              resize: 'vertical',
            }}
          />
        ) : (
          <MathText text={result.question_text || '(未识别到文字)'} />
        )}
      </Section>

      {/* 学生答案 */}
      {result.student_answer.detected && (
        <Section title="✏️ 孩子的答案">
          {editable ? (
            <input
              type="text"
              value={result.student_answer.text || ''}
              onChange={e => updateField('student_answer', { ...result.student_answer, text: e.target.value })}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '14px',
              }}
            />
          ) : (
            <MathText text={result.student_answer.text || ''} />
          )}
        </Section>
      )}

      {/* 正确答案 */}
      <Section title="✅ 正确答案">
        {editable ? (
          <textarea
            value={result.correct_answer}
            onChange={e => updateField('correct_answer', e.target.value)}
            style={{
              width: '100%',
              minHeight: '60px',
              padding: '8px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontSize: '14px',
              lineHeight: 1.7,
              resize: 'vertical',
            }}
          />
        ) : (
          <MathText text={result.correct_answer} style={{ whiteSpace: 'pre-wrap' }} />
        )}
      </Section>

      {/* 解题过程 */}
      {result.solution_steps && (
        <Section title="📝 解题过程">
          {editable ? (
            <textarea
              value={result.solution_steps}
              onChange={e => updateField('solution_steps', e.target.value)}
              style={{
                width: '100%',
                minHeight: '80px',
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '14px',
                lineHeight: 1.7,
                resize: 'vertical',
              }}
            />
          ) : (
            <MathText text={result.solution_steps} style={{ whiteSpace: 'pre-wrap' }} />
          )}
        </Section>
      )}

      {/* 错误分析 */}
      {result.error_analysis && (
        <Section title="🔍 错误分析">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {editable ? (
              <>
                <EditableField
                  label="错误点"
                  value={result.error_analysis.error_point || ''}
                  onChange={v => updateErrorAnalysis('error_point', v)}
                />
                <EditableField
                  label="错误类型"
                  value={result.error_analysis.error_type || ''}
                  onChange={v => updateErrorAnalysis('error_type', v)}
                />
                <EditableField
                  label="错因诊断"
                  value={result.error_analysis.root_cause || ''}
                  onChange={v => updateErrorAnalysis('root_cause', v)}
                />
                <EditableField
                  label="建议"
                  value={result.error_analysis.suggestion || ''}
                  onChange={v => updateErrorAnalysis('suggestion', v)}
                />
              </>
            ) : (
              <>
                {result.error_analysis.error_point && (
                  <Field label="错误点" value={result.error_analysis.error_point} />
                )}
                {result.error_analysis.error_type && (
                  <Field label="错误类型" value={result.error_analysis.error_type} />
                )}
                {result.error_analysis.root_cause && (
                  <Field label="错因诊断" value={result.error_analysis.root_cause} />
                )}
                {result.error_analysis.suggestion && (
                  <Field label="建议" value={result.error_analysis.suggestion} />
                )}
              </>
            )}
          </div>
        </Section>
      )}

      {/* 元数据 - 可编辑 */}
      {editable ? (
        <div style={{
          marginTop: '16px',
          padding: '12px',
          background: '#f8f9fa',
          borderRadius: 'var(--radius-sm)',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
        }}>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>知识点</label>
            <input
              type="text"
              value={result.metadata.knowledge_points.join(', ')}
              onChange={e => updateMetadata('knowledge_points', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="用逗号分隔"
              style={{
                width: '100%',
                padding: '6px 8px',
                marginTop: '4px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
              }}
            />
          </div>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>难度</label>
            <select
              value={result.metadata.difficulty}
              onChange={e => updateMetadata('difficulty', e.target.value)}
              style={{
                width: '100%',
                padding: '6px 8px',
                marginTop: '4px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
              }}
            >
              <option value="简单">简单</option>
              <option value="中等">中等</option>
              <option value="较难">较难</option>
            </select>
          </div>
        </div>
      ) : (
        <div style={{
          marginTop: '16px',
          padding: '10px 14px',
          background: '#f8f9fa',
          borderRadius: 'var(--radius-sm)',
          fontSize: '13px',
          color: 'var(--color-text-secondary)',
          display: 'flex',
          gap: '16px',
          flexWrap: 'wrap',
        }}>
          <span>📚 {result.metadata.topic}</span>
          <span>📊 {result.metadata.difficulty}</span>
          <span>🏷 {result.metadata.knowledge_points.join('、') || '无'}</span>
        </div>
      )}
    </div>
  )
}

/** 带数学公式渲染的文本 */
function MathText({ text, style }: { text: string; style?: React.CSSProperties }) {
  const html = renderMathInText(text)
  return (
    <p
      style={{ margin: 0, lineHeight: 1.7, ...style }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '16px' }}>
      <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 6px 0', color: 'var(--color-text)' }}>
        {title}
      </h4>
      {children}
    </div>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: '8px', fontSize: '14px' }}>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0, minWidth: '64px' }}>
        {label}：
      </span>
      <MathText text={value} />
    </div>
  )
}

function EditableField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', gap: '8px', fontSize: '14px', alignItems: 'flex-start' }}>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0, minWidth: '64px', paddingTop: '6px' }}>
        {label}：
      </span>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          flex: 1,
          padding: '6px 8px',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--color-border)',
          fontSize: '14px',
        }}
      />
    </div>
  )
}
