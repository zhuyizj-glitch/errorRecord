/**
 * AI 分析结果预览
 *
 * 一张照片通常含多道题，所以这里是**题目列表**：每道题一张卡片、各自可勾选，
 * 用户挑出要入库的题，保存时逐题生成独立的错题记录。
 *
 * 勾选默认不在这里决定，由调用方（UploadPage）根据 AI 的初判给出初始值，
 * 因为「看起来做对了」并不等于掌握 —— 订正过的题尤其如此。
 */

import {
  BarChart3,
  BookOpen,
  CircleCheck,
  CircleX,
  FileText,
  Pencil,
  ScrollText,
  Search,
  Tag,
  type LucideIcon,
} from 'lucide-react'
import type { AnalyzeResult, QuestionAnalysis } from '../types'
import { renderMathInText } from '../utils/mathRenderer'

interface Props {
  result: AnalyzeResult | null
  /** 已勾选（待入库）的题目索引 */
  selected: Set<number>
  onToggleSelect: (index: number) => void
  editable?: boolean
  /** 编辑模式下内容变化时回调，参数是更新后的完整题目数组 */
  onChange?: (questions: QuestionAnalysis[]) => void
}

export default function AnalysisPreview({
  result,
  selected,
  onToggleSelect,
  editable = false,
  onChange,
}: Props) {
  if (!result) return <p style={{ color: 'var(--color-text-secondary)' }}>暂无分析结果</p>

  const questions = result.questions ?? []
  if (!questions.length) {
    return <p style={{ color: 'var(--color-text-secondary)' }}>没能从这张图片里识别出题目</p>
  }

  const replaceAt = (index: number, next: QuestionAnalysis) => {
    if (!onChange) return
    const copy = questions.slice()
    copy[index] = next
    onChange(copy)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {questions.length > 1 && (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-secondary)' }}>
          这张图片里识别出 <strong style={{ color: 'var(--color-text)' }}>{questions.length}</strong> 道题，
          勾选你要入库的（默认勾选「看起来做错」和「有订正」的题）。
        </p>
      )}

      {questions.map((q, i) => (
        <QuestionCard
          key={i}
          question={q}
          index={i}
          checked={selected.has(i)}
          onToggle={() => onToggleSelect(i)}
          editable={editable}
          onChange={next => replaceAt(i, next)}
        />
      ))}
    </div>
  )
}

/** 单道题的卡片 */
function QuestionCard({
  question: q,
  index,
  checked,
  onToggle,
  editable,
  onChange,
}: {
  question: QuestionAnalysis
  index: number
  checked: boolean
  onToggle: () => void
  editable: boolean
  onChange: (next: QuestionAnalysis) => void
}) {
  const update = (patch: Partial<QuestionAnalysis>) => onChange({ ...q, ...patch })
  const updateError = (field: string, value: string) =>
    onChange({ ...q, error_analysis: { ...(q.error_analysis || {}), [field]: value } })
  const updateMeta = (field: string, value: unknown) =>
    onChange({ ...q, metadata: { ...q.metadata, [field]: value } })

  return (
    <div
      style={{
        border: `1.5px solid ${checked ? 'var(--color-primary)' : 'var(--color-border)'}`,
        borderRadius: 'var(--radius-md)',
        background: checked ? 'var(--color-surface)' : 'rgba(120, 120, 128, 0.08)',
        padding: 16,
        transition: 'border-color 150ms, background 150ms',
      }}
    >
      {/* 头部：勾选 + 题号 + 状态标记 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          style={{ width: 18, height: 18, cursor: 'pointer', accentColor: 'var(--color-primary)', flexShrink: 0 }}
        />
        <button
          onClick={onToggle}
          style={{
            background: 'none', border: 'none', padding: 0,
            fontWeight: 700, fontSize: 15, color: 'var(--color-text)', cursor: 'pointer',
          }}
        >
          {q.number ? `第 ${q.number} 题` : `第 ${index + 1} 题`}
        </button>
        <StatusBadges question={q} />
      </div>

      <div style={{ opacity: checked ? 1 : 0.6 }}>
        {/* 题目 */}
        <Section title="题目内容" Icon={FileText}>
          {editable ? (
            <EditableMathText
              value={q.question_text || ''}
              onChange={v => update({ question_text: v })}
              minHeight={60}
            />
          ) : (
            <MathText text={q.question_text || '(未识别到文字)'} />
          )}
        </Section>

        {/* 孩子作答 */}
        {q.has_correction && (
          <Section title="孩子作答（已订正）" Icon={Pencil}>
            <MathText text={q.student_answer?.text || '(未识别到)'} />
          </Section>
        )}
        {!q.has_correction && q.student_answer?.detected && (
          <Section title="孩子的答案" Icon={Pencil}>
            {editable ? (
              <EditableMathText
                value={q.student_answer.text || ''}
                onChange={v => update({ student_answer: { ...q.student_answer, text: v } })}
                minHeight={38}
              />
            ) : (
              <MathText text={q.student_answer.text || ''} />
            )}
          </Section>
        )}

        {/* 正确答案 */}
        <Section title="正确答案" Icon={CircleCheck}>
          {editable ? (
            <EditableMathText
              value={q.correct_answer || ''}
              onChange={v => update({ correct_answer: v })}
              minHeight={60}
            />
          ) : (
            <MathText text={q.correct_answer || ''} style={{ whiteSpace: 'pre-wrap' }} />
          )}
        </Section>

        {/* 解题过程 */}
        {q.solution_steps && (
          <Section title="解题过程" Icon={ScrollText}>
            {editable ? (
              <EditableMathText
                value={q.solution_steps}
                onChange={v => update({ solution_steps: v })}
                minHeight={80}
              />
            ) : (
              <MathText text={q.solution_steps} style={{ whiteSpace: 'pre-wrap' }} />
            )}
          </Section>
        )}

        {/* 错误分析（做对的题 AI 不会给，所以整段可能不出现） */}
        {q.error_analysis && (
          <Section title="错误分析" Icon={Search}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {editable ? (
                <>
                  <EditableField label="错误点" value={q.error_analysis.error_point || ''} onChange={v => updateError('error_point', v)} />
                  <EditableField label="错误类型" value={q.error_analysis.error_type || ''} onChange={v => updateError('error_type', v)} />
                  <EditableField label="错因诊断" value={q.error_analysis.root_cause || ''} onChange={v => updateError('root_cause', v)} />
                  <EditableField label="建议" value={q.error_analysis.suggestion || ''} onChange={v => updateError('suggestion', v)} />
                </>
              ) : (
                <>
                  {q.error_analysis.error_point && <Field label="错误点" value={q.error_analysis.error_point} />}
                  {q.error_analysis.error_type && <Field label="错误类型" value={q.error_analysis.error_type} />}
                  {q.error_analysis.root_cause && <Field label="错因诊断" value={q.error_analysis.root_cause} />}
                  {q.error_analysis.suggestion && <Field label="建议" value={q.error_analysis.suggestion} />}
                </>
              )}
            </div>
          </Section>
        )}

        {/* 元数据 */}
        <div style={{
          marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--color-border)',
          display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13,
          color: 'var(--color-text-secondary)',
        }}>
          {editable ? (
            <>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>知识点</span>
                <input
                  type="text"
                  value={(q.metadata.knowledge_points || []).join(', ')}
                  onChange={e => updateMeta('knowledge_points', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                  placeholder="用逗号分隔"
                  style={{ ...textareaStyle(0), minHeight: 34, width: 180 }}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>难度</span>
                <select
                  value={q.metadata.difficulty || '中等'}
                  onChange={e => updateMeta('difficulty', e.target.value)}
                  style={{ ...textareaStyle(0), minHeight: 34, width: 90 }}
                >
                  <option value="简单">简单</option>
                  <option value="中等">中等</option>
                  <option value="较难">较难</option>
                </select>
              </label>
            </>
          ) : (
            <>
              {q.metadata.topic && (
                <span><BookOpen size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />{q.metadata.topic}</span>
              )}
              {(q.metadata.knowledge_points || []).length > 0 && (
                <span><Tag size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />{q.metadata.knowledge_points.join('、')}</span>
              )}
              {q.metadata.difficulty && (
                <span><BarChart3 size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />{q.metadata.difficulty}</span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

/** 状态徽章：做对/做错 + 订正痕迹 + 识别置信度 */
function StatusBadges({ question: q }: { question: QuestionAnalysis }) {
  const badges: React.ReactNode[] = []

  if (q.has_correction) {
    badges.push(
      <Badge key="correction" tone="warning" label="有订正痕迹" title="订正过不代表掌握，建议入库盯一段时间" />,
    )
  }
  if (!q.looks_correct) {
    badges.push(<Badge key="wrong" tone="error" label="看起来做错了" />)
  } else if (!q.has_correction) {
    badges.push(<Badge key="ok" tone="success" label="看起来做对了" />)
  }
  if (q.confidence === 'low') {
    badges.push(<Badge key="conf" tone="neutral" label="识别存疑" title="图片模糊，建议核对" />)
  }

  return <>{badges}</>
}

function Badge({
  tone, label, title,
}: {
  tone: 'success' | 'error' | 'warning' | 'neutral'
  label: string
  title?: string
}) {
  const color = {
    success: 'var(--color-success)',
    error: 'var(--color-error)',
    warning: 'var(--color-warning)',
    neutral: 'var(--color-text-secondary)',
  }[tone]

  return (
    <span
      title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 9px', borderRadius: 999,
        fontSize: 12, fontWeight: 500,
        color, background: `color-mix(in srgb, ${color} 15%, transparent)`,
      }}
    >
      {tone === 'success' && <CircleCheck size={12} />}
      {tone === 'error' && <CircleX size={12} />}
      {label}
    </span>
  )
}

// ── 以下为通用小部件 ──────────────────────────────────────────

const textareaStyle = (minHeight: number): React.CSSProperties => ({
  width: '100%',
  minHeight: minHeight || undefined,
  padding: '8px 10px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface-2)',
  color: 'var(--color-text)',
  fontSize: 14,
  lineHeight: 1.7,
  fontFamily: 'inherit',
  resize: minHeight ? 'vertical' : 'none',
})

function Section({
  title, Icon, children,
}: {
  title: string
  Icon: LucideIcon
  children: React.ReactNode
}) {
  return (
    <div style={{ marginBottom: 16, color: 'var(--color-text)' }}>
      <h4 style={{
        fontSize: 14, fontWeight: 600, margin: '0 0 6px 0',
        color: 'var(--color-text-secondary)',
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <Icon size={14} />
        {title}
      </h4>
      {children}
    </div>
  )
}

/** 带数学公式渲染的文本 */
function MathText({ text, style }: { text: string; style?: React.CSSProperties }) {
  const html = renderMathInText(text)
  return (
    <p
      style={{ margin: 0, lineHeight: 1.7, color: 'inherit', ...style }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 14 }}>
      <span style={{ color: 'var(--color-text-secondary)', flexShrink: 0, minWidth: 64 }}>
        {label}：
      </span>
      <MathText text={value} />
    </div>
  )
}

function EditableField({
  label, value, onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <span style={{
        color: 'var(--color-text-secondary)', flexShrink: 0, minWidth: 64,
        fontSize: 14, lineHeight: 1.7, paddingTop: 6,
      }}>
        {label}：
      </span>
      <div style={{ flex: 1 }}>
        <EditableMathText value={value} onChange={onChange} minHeight={48} />
      </div>
    </div>
  )
}

/**
 * 可编辑的公式字段：textarea + 实时 KaTeX 预览。
 * 面向数学的录入需要「边改边看」——用户改 LaTeX 时立刻看到渲染结果，
 * 改错了（比如 \frac 的花括号没闭合）也能当场发现，而不是保存后才暴露。
 */
function EditableMathText({
  value, onChange, minHeight = 60,
}: {
  value: string
  onChange: (v: string) => void
  minHeight?: number
}) {
  return (
    <div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="数学公式用 $...$ 或 $$...$$"
        style={textareaStyle(minHeight)}
      />
      <div style={{
        marginTop: 6,
        padding: '8px 12px',
        border: '1px dashed var(--color-border)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--color-surface)',
        minHeight: 30,
      }}>
        <MathText text={value || '　'} />
      </div>
    </div>
  )
}
