/**
 * 数学公式渲染工具
 * 使用 KaTeX 渲染 LaTeX 公式，支持 $...$ 和 $$...$$ 格式
 */

import katex from 'katex'
import 'katex/dist/katex.min.css'

/**
 * 渲染单个 LaTeX 公式为 HTML
 */
export function renderLatex(latex: string, displayMode: boolean = false): string {
  try {
    return katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      errorColor: '#ef4444',
      trust: false,
    })
  } catch (e) {
    return `<span style="color: #ef4444;">[公式错误: ${latex}]</span>`
  }
}

/**
 * 处理文本中的 LaTeX 公式
 * 将 $...$ 和 $$...$$ 替换为渲染后的 HTML
 */
export function renderMathInText(text: string): string {
  if (!text) return ''

  let result = text

  // 处理 $$...$$ (display mode)
  result = result.replace(/\$\$([\s\S]+?)\$\$/g, (_match, latex) => {
    return renderLatex(latex.trim(), true)
  })

  // 处理 $...$ (inline mode)，但排除已经处理的 $$
  result = result.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (_match, latex) => {
    return renderLatex(latex.trim(), false)
  })

  return result
}

/**
 * 简易 Markdown 渲染（带数学公式支持）
 */
export function renderMarkdownWithMath(text: string): string {
  if (!text) return ''

  // 先处理数学公式（避免被 markdown 处理破坏）
  const mathPlaceholders: string[] = []
  let processed = text

  // 占位 $$...$$
  processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (_match, latex) => {
    const placeholder = `%%MATH_BLOCK_${mathPlaceholders.length}%%`
    mathPlaceholders.push(renderLatex(latex.trim(), true))
    return placeholder
  })

  // 占位 $...$
  processed = processed.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (_match, latex) => {
    const placeholder = `%%MATH_INLINE_${mathPlaceholders.length}%%`
    mathPlaceholders.push(renderLatex(latex.trim(), false))
    return placeholder
  })

  // 处理 Markdown
  let html = processed
    .replace(/^### (.+)$/gm, '<h4 style="margin: 16px 0 8px; font-size: 15px; font-weight: 600;">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 style="margin: 20px 0 10px; font-size: 17px; font-weight: 700;">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 style="margin: 24px 0 12px; font-size: 20px; font-weight: 700;">$1</h2>')
    .replace(/^\*\*(.+?)：?\*\*\s*(.*)$/gm, '<p style="margin: 6px 0;"><strong style="color: var(--color-text-secondary);">$1：</strong> $2</p>')
    .replace(/^!\[.*?\]\((.+?)\)$/gm, '<img src="$1" style="max-width: 100%; border-radius: 8px; margin: 8px 0;" />')
    .replace(/^>\s*(.+)$/gm, '<blockquote style="margin: 8px 0; padding: 8px 16px; border-left: 3px solid var(--color-primary); background: #f8f9fa; border-radius: 0 6px 6px 0;">$1</blockquote>')
    .replace(/\n\n/g, '<br/><br/>')

  // 替换回数学公式
  mathPlaceholders.forEach((rendered, i) => {
    html = html.replace(`%%MATH_BLOCK_${i}%%`, rendered)
    html = html.replace(`%%MATH_INLINE_${i}%%`, rendered)
  })

  return html
}
