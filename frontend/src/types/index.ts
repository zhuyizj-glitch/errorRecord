/** 类型定义 */

export interface Child {
  id: string
  name: string
  emoji: string
  subjects: string[]
  current_stage?: string
}

export interface ChildrenResponse { children: Child[]; available_subjects: string[]; available_stages: string[] }

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

// ── v2.0 真题库（三形态模型）──────────────────────────────────

export type ZhentiForm = 'independent' | 'material_group' | 'passage'

/** 材料组题/语篇整题的子题（各自独立打标） */
export interface ZhentiSubQuestion {
  number?: string
  question_text: string
  correct_answer: string
  solution_steps?: string
  knowledge_points: string[]
  era?: string
  module?: string
}

/** 真题库条目（账号级资源） */
export interface ZhentiQuestion {
  id: string
  account_id: string
  subject: string
  year: string
  source: string
  stage?: string
  number?: string
  question_form: ZhentiForm
  question_type?: string
  rating?: string
  topic?: string
  knowledge_points: string[]
  era?: string
  module?: string
  difficulty: string
  has_diagram?: boolean
  diagram_description?: string
  passage?: string
  sub_questions?: ZhentiSubQuestion[]
  created_at: string
  practice_count: number
  correct_count: number
  wrong_count: number
  last_practice_at?: string | null
  practice_history?: Array<{ date: string; child_id: string; result: string; note?: string; sub_number?: string }>
  converted_to?: Array<{ child_id: string; child_name: string; question_id: string; sub_number?: string; date: string }>
  _file?: string
  _body?: string
  _question?: string
  _answer?: string
  _solution?: string
  _structured?: boolean
}

/** AI 拆出的题目单元 */
export interface ZhentiAnalysisItem {
  number?: string
  question_form: ZhentiForm
  question_type?: string
  rating?: string
  passage?: string
  question_text: string
  has_diagram?: boolean
  diagram_description?: string
  correct_answer: string
  solution_steps?: string
  topic?: string
  knowledge_points: string[]
  era?: string
  module?: string
  difficulty: string
  confidence?: string
  sub_questions?: ZhentiSubQuestion[]
}

export interface ZhentiAnalyzeResult {
  subject?: string
  questions: ZhentiAnalysisItem[]
}

export interface ZhentiTask {
  id: string
  account_id: string
  child_id: string
  subject: string
  image_ids: Array<{ id: string; path: string; filename: string }>
  kind: string
  meta: { year?: string; source?: string; stage?: string }
  status: 'pending' | 'processing' | 'completed' | 'failed'
  result?: ZhentiAnalyzeResult
  error?: string
  created_at: string
  completed_at?: string
}

export interface WeakPoint {
  knowledge_point: string
  weight: number
  question_count: number
  avg_mastery: number
}

export interface ZhentiRecommendation extends ZhentiQuestion {
  match_score: number
  matched_points: string[]
  matched_sub_numbers?: string[]
  child_practice_count: number
}

/** 题库筛选维度 */
export interface ZhentiDimensions {
  eras: string[]
  modules: string[]
  question_types: string[]
  ratings: string[]
  stages: string[]
}
