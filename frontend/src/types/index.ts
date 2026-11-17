/** 类型定义 */

export interface Child {
  id: string
  name: string
  emoji: string
  subjects: string[]
}

export interface ChildrenResponse { children: Child[]; available_subjects: string[] }

export interface Account {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'user'
  must_change_password: boolean
}

export interface Question {
  id: string
  child_id: string
  child_name?: string
  subject: string
  topic: string
  error_type?: string
  source_type: string
  difficulty: string
  error_date: string
  created_at: string
  redo_count: number
  mastery_score: number
  mastery_level: string
  mastery_status: string
  knowledge_points: string[]
  tags: string[]
  next_review_date?: string
  review_interval_days?: number
  redo_history?: Array<{ date: string; result: string; note?: string }>
  repeat_streak?: number
  repeat_pattern?: boolean
  error_suggestion?: string
  _file?: string

  // ── 后端在 /review/plan 与 /questions/{id} 响应里附加的派生字段 ──
  // `_` 前缀表示「只在响应里存在，不进存储」（file_ops._build_markdown 会过滤）
  _body?: string
  /** 题干（已从正文解析出来，去掉了 `> **题目内容**：` 外壳） */
  _question?: string
  _answer?: string
  _solution?: string
  _error_analysis?: string
  _parent_note?: string
  /** 正文是否被成功解析成段落。false 时调用方应整段渲染 _body，不要留空白 */
  _structured?: boolean

  // 练习题标记（AI 生成，与错题区分；默认列表与统计会排除它）
  is_practice?: boolean
  practice_batch_id?: string
}

/** 图片里拆出来的单道题 */
export interface QuestionAnalysis {
  /** 题号，如 "10"。图中没标号时为空 */
  number?: string
  /** AI 初判「看起来做对了没有」。仅供参考，不用于自动筛选 */
  looks_correct: boolean
  /** 有没有订正痕迹（划掉重写、红笔修改等）。订正过不代表掌握 */
  has_correction: boolean
  source_type: string
  question_text: string
  has_diagram?: boolean
  diagram_description?: string
  student_answer: {
    detected: boolean
    text?: string
    confidence?: string
  }
  correct_answer: string
  solution_steps?: string
  error_analysis?: {
    error_point?: string
    error_type?: string
    root_cause?: string
    suggestion?: string
  }
  metadata: {
    topic: string
    knowledge_points: string[]
    difficulty: string
  }
  confidence: string
}

/** AI 分析结果。一张图可能含多道题，所以题目是列表 */
export interface AnalyzeResult {
  /** AI 判断的学科，前端据此自动更正任务的学科 */
  subject?: string
  questions: QuestionAnalysis[]
}

export interface LLMSettings {
  api_base: string
  api_key: string
  model: string
  system_prompt?: string
  timeout?: number
}
