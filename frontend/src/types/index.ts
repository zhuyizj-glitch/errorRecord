/** 类型定义 */

export interface Child {
  name: string
  emoji: string
  subjects: string[]
}

export interface ChildrenMap {
  [key: string]: Child
}

export interface Question {
  id: string
  child: string
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
}

export interface AnalyzeResult {
  source_type: string
  question_text: string
  has_diagram: boolean
  diagram_description?: string
  student_answer: {
    detected: boolean
    text?: string
    confidence?: string
  }
  correct_answer: string
  solution_steps: string
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

export interface LLMSettings {
  api_base: string
  api_key: string
  model: string
  system_prompt?: string
  timeout?: number
}
