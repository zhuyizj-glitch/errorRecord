/** 上传错题页面 - 异步任务列表模式 */

import { useState, useEffect, useRef } from 'react'
import {
  AlertTriangle,
  CircleCheck,
  CircleX,
  Clock,
  ListChecks,
  LoaderCircle,
  Pencil,
  RefreshCw,
  RotateCw,
  Save,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { useStore } from '../store/useStore'
import ImageUploader from '../components/ImageUploader'
import AnalysisPreview from '../components/AnalysisPreview'
import { createQuestion } from '../api/client'
import type { AnalyzeResult, QuestionAnalysis } from '../types'

/** 后端上传接口返回的图片信息 */
interface UploadedImage {
  id: string
  path: string
  filename: string
}

interface Task {
  id: string
  child_id: string
  subject: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  result: AnalyzeResult | null
  error: string | null
  created_at: string
  completed_at: string | null
  expanded: boolean
  imageFiles: File[]
  /** 后端返回的图片信息（含临时文件路径），保存错题时要回传给后端 */
  uploadedImages: UploadedImage[]
  editMode: boolean
  refineFeedback: string
  /** 勾选待入库的题目索引，对应 result.questions 的下标 */
  selected: Set<number>
  /** 是否已经按 AI 初判给过默认勾选（避免用户取消勾选后被再次覆盖） */
  selectionInitialized: boolean
}

export default function UploadPage() {
  const { currentChild, currentSubject, children } = useStore()
  const [files, setFiles] = useState<File[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  /** 上传中（从点按钮到任务创建完成的这段，用户需要看到反馈） */
  const [uploading, setUploading] = useState(false)
  /** 指向任务列表，新任务创建后滚过去 */
  const tasksSectionRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // 获取所有学科列表
  const allSubjects = children.find(child => child.id === currentChild)?.subjects || []

  // 轮询任务状态 - 使用 ref 避免闭包问题
  const tasksRef = useRef(tasks)
  tasksRef.current = tasks
  // children 在轮询的 useEffect 里要用到，但那个 effect 的依赖是空数组，
  // 直接闭包捕获会永远拿到初始值（空数组），所以同样用 ref 兜住
  const childrenRef = useRef(children)
  childrenRef.current = children

  useEffect(() => {
    const poll = async () => {
      const currentTasks = tasksRef.current
      const pendingTasks = currentTasks.filter(t => t.status === 'pending' || t.status === 'processing')

      for (const task of pendingTasks) {
        try {
          const res = await fetch(`/api/tasks/${task.id}`).then(r => r.json())
          if (res.status !== task.status || JSON.stringify(res.result) !== JSON.stringify(task.result)) {
            setTasks(prev => prev.map(t => {
              if (t.id !== task.id) return t
              const next = {
                ...t,
                status: res.status,
                result: res.result,
                error: res.error,
                completed_at: res.completed_at,
              }
              // 分析完成后，用 AI 判断出的学科自动选中。
              // 上传时选的学科是凭印象挑的，AI 看过题目内容后判断更准。
              // 只在「这门课确实属于这个孩子」时才改，否则会选到一个不存在的选项。
              const guessed = res.result?.subject
              if (res.status === 'completed' && guessed) {
                const child = childrenRef.current.find(c => c.id === t.child_id)
                if (child?.subjects?.includes(guessed)) next.subject = guessed
              }
              // 首次拿到结果时按 AI 初判给个默认勾选：做错的 + 有订正痕迹的。
              // 只做一次，之后用户的勾选不会再被覆盖。
              const qs = res.result?.questions as QuestionAnalysis[] | undefined
              if (res.status === 'completed' && qs?.length && !next.selectionInitialized) {
                next.selected = new Set(
                  qs.map((q, i) => (!q.looks_correct || q.has_correction) ? i : -1).filter(i => i >= 0),
                )
                next.selectionInitialized = true
              }
              return next
            }))
          }
        } catch (e) {
          console.error('Poll error:', e)
        }
      }
    }

    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])

  const handleStartAnalysis = async () => {
    if (!files.length || !currentChild || !currentSubject) return
    setError('')
    setNotice('')
    setUploading(true)

    try {
      // 1. 上传图片
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      const uploadResponse = await fetch('/api/upload/images', { method: 'POST', body: form })
      const uploadRes = await uploadResponse.json().catch(() => ({}))

      if (!uploadResponse.ok) {
        setError(uploadRes.detail || '上传失败')
        return
      }
      if (!uploadRes.image_ids?.length) {
        setError('上传失败')
        return
      }
      setNotice(uploadRes.warnings?.join('；') || '')

      // 2. 为每张图片单独创建一个分析任务
      //
      // 为什么不一次把多张图交给同一个任务：那样 AI 要在一轮里输出所有题的分析，
      // 输出量随图片数线性增长，很容易撞上超时（实测 5 张图跑到 62 秒被掐断）。
      // 拆成一个个任务后，每张图的分析都短，而且**完成一张就能立刻看到一张的结果**。
      // 后端用锁保证串行执行，不会同时打满 AI 服务的并发限制。
      const created: Task[] = []

      for (let i = 0; i < uploadRes.image_ids.length; i++) {
        const img = uploadRes.image_ids[i]
        const taskRes = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            child_id: currentChild,
            subject: currentSubject,
            image_ids: [img],
          }),
        }).then(r => r.json())

        created.push({
          id: taskRes.task_id,
          child_id: currentChild,
          subject: currentSubject,
          status: 'pending',
          result: null,
          error: null,
          created_at: taskRes.created_at,
          completed_at: null,
          expanded: true,
          imageFiles: files[i] ? [files[i]] : [],
          uploadedImages: [img],
          editMode: false,
          refineFeedback: '',
          selected: new Set<number>(),
          selectionInitialized: false,
        })
      }

      // 按上传顺序插到列表最前面
      setTasks(prev => [...created, ...prev])
      setFiles([])

      // 任务卡片在页面下方，而新任务插在列表顶部 —— 不滚过去的话，
      // 用户点完「开始分析」会觉得什么都没发生（其实后台已经在跑了）。
      requestAnimationFrame(() => {
        tasksSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (e: any) {
      setError('创建任务失败: ' + (e.message || e))
    } finally {
      setUploading(false)
    }
  }

  const handleSave = async (task: Task) => {
    const questions = task.result?.questions ?? []
    // 只保存勾选中的题。默认勾选的是 AI 初判「做错」和「有订正」的，
    // 但以用户的实际勾选为准 —— 订正过不代表掌握，AI 判断只是初判。
    const picked = questions.filter((_, i) => task.selected.has(i))
    if (!picked.length) {
      setError('请至少勾选一道题再保存')
      return
    }

    try {
      // 用北京时间的今天。toISOString() 给的是 UTC 日期，
      // 北京时间凌晨 0-8 点之间会记成前一天。
      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' })

      // 逐题保存：每道题生成一个独立的错题记录
      for (const q of picked) {
        await createQuestion({
          child_id: task.child_id,
          subject: task.subject,
          topic: q.metadata?.topic || '',
          error_type: q.error_analysis?.error_type || null,
          source_type: q.source_type,
          difficulty: q.metadata?.difficulty || '中等',
          error_date: today,
          question_text: q.question_text,
          correct_answer: q.correct_answer,
          solution_steps: q.solution_steps,
          error_analysis: q.error_analysis,
          error_suggestion: q.error_analysis?.suggestion,
          knowledge_points: q.metadata?.knowledge_points || [],
          tags: ['错题'],
          // 不提交图片：原图只是分析输入，保存的只有分析结果
        })
      }
      setTasks(prev => prev.filter(t => t.id !== task.id))
      setNotice(`已保存 ${picked.length} 道错题`)
    } catch (e: any) {
      setError('保存失败: ' + (e.message || e))
    }
  }

  const handleRetry = async (task: Task) => {
    setTasks(prev => prev.filter(t => t.id !== task.id))
    setFiles(task.imageFiles)
    setTimeout(() => handleStartAnalysis(), 100)
  }

  const handleRegenerate = async (task: Task) => {
    // 重新创建任务进行分析
    setTasks(prev => prev.map(t =>
      t.id === task.id ? { ...t, status: 'pending', result: null, error: null } : t
    ))

    try {
      const form = new FormData()
      task.imageFiles.forEach(f => form.append('files', f))
      const uploadResponse = await fetch('/api/upload/images', { method: 'POST', body: form })
      const uploadRes = await uploadResponse.json().catch(() => ({}))

      if (!uploadResponse.ok) {
        setError(uploadRes.detail || '重新分析失败')
        return
      }

      await fetch(`/api/tasks/${task.id}/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_ids: uploadRes.image_ids }),
      })

      // 任务会自动更新状态通过轮询
    } catch (e: any) {
      setError('重新分析失败: ' + (e.message || e))
    }
  }

  const handleRefine = async (task: Task) => {
    if (!task.refineFeedback.trim()) return

    setTasks(prev => prev.map(t =>
      t.id === task.id ? { ...t, status: 'processing', refineFeedback: '' } : t
    ))

    try {
      await fetch(`/api/tasks/${task.id}/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feedback: task.refineFeedback,
          current_result: task.result,
        }),
      })
    } catch (e: any) {
      setError('优化失败: ' + (e.message || e))
    }
  }

  const handleDismiss = (taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId))
    fetch(`/api/tasks/${taskId}`, { method: 'DELETE' }).catch(() => {})
  }

  const toggleExpand = (taskId: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, expanded: !t.expanded } : t))
  }

  const toggleEditMode = (taskId: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, editMode: !t.editMode } : t))
  }

  /** 勾选/取消勾选某道题 */
  const toggleQuestionSelection = (taskId: string, index: number) => {
    setTasks(prev => prev.map(t => {
      if (t.id !== taskId) return t
      const next = new Set(t.selected)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return { ...t, selected: next }
    }))
  }

  /** 编辑模式下改动某道题的内容 */
  const updateTaskQuestions = (taskId: string, questions: QuestionAnalysis[]) => {
    setTasks(prev => prev.map(t =>
      t.id === taskId && t.result ? { ...t, result: { ...t.result, questions } } : t
    ))
  }

  const updateTaskRefineFeedback = (taskId: string, feedback: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, refineFeedback: feedback } : t))
  }

  const updateTaskChild = (taskId: string, child_id: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, child_id } : t))
  }

  const updateTaskSubject = (taskId: string, subject: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, subject } : t))
  }

  const statusConfig = {
    pending: { Icon: Clock, color: '#8e8e93', label: '等待中' },
    processing: { Icon: LoaderCircle, color: '#007aff', label: '分析中' },
    completed: { Icon: CircleCheck, color: '#34c759', label: '完成' },
    failed: { Icon: CircleX, color: '#ff3b30', label: '失败' },
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
        <h2 style={{ margin: 0 }}>上传错题</h2>
        <span style={{
          background: 'var(--color-primary-light)',
          color: 'var(--color-primary)',
          padding: '4px 12px',
          borderRadius: '20px',
          fontSize: '13px',
          fontWeight: 500,
        }}>
          {children.find(child => child.id === currentChild)?.emoji}{' '}
          {children.find(child => child.id === currentChild)?.name}
          {currentSubject ? ` · ${currentSubject}` : ''}
        </span>
      </div>
      {/* 学科选「全部」时不能上传 —— 错题必须归到某一门课下，否则没法归档 */}
      {!currentSubject ? (
        <p style={{
          color: 'var(--color-warning)',
          marginBottom: '20px',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          <AlertTriangle size={15} />
          当前学科选的是「全部」，上传前请先在上方选择一门具体学科
        </p>
      ) : (
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '20px', fontSize: '14px' }}>
          上传后会自动开始 AI 分析，你可以继续上传其他题目
        </p>
      )}

      {/* 上传区域 */}
      <div style={{
        background: 'var(--color-surface)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-sm)',
        border: '1px solid var(--color-border)',
      }}>
        <ImageUploader files={files} setFiles={setFiles} />

        <div style={{ marginTop: '20px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={handleStartAnalysis}
            disabled={!files.length || uploading || !currentSubject}
            style={{
              padding: '10px 28px',
              fontSize: '15px',
              fontWeight: 600,
              background: 'var(--color-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
            }}
          >
            {uploading
              ? <>
                  <LoaderCircle size={16} className="icon-spin" style={{ verticalAlign: '-2px', marginRight: 5 }} />
                  上传中…
                </>
              : <>
                  <Sparkles size={16} style={{ verticalAlign: '-2px', marginRight: 5 }} />
                  开始分析
                </>}
          </button>
          {files.length > 0 && (
            <button
              onClick={() => setFiles([])}
              style={{
                padding: '10px 20px',
                fontSize: '14px',
                background: 'transparent',
                color: 'var(--color-text-secondary)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              清空
            </button>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          background: 'var(--color-error-light)',
          border: '1px solid #ffcdd2',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-error)',
          fontSize: '14px',
        }}>
          {error}
        </div>
      )}

      {/* 非阻断性提示（例如分辨率偏低） */}
      {notice && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          background: 'var(--color-warning-light)',
          border: '1px solid rgba(255, 159, 10, 0.35)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-warning)',
          fontSize: '14px',
        }}>
          {notice}
        </div>
      )}

      {/* 任务列表 */}
      {tasks.length > 0 && (
        <div ref={tasksSectionRef} style={{ marginTop: '24px', scrollMarginTop: '80px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <ListChecks size={16} />
            分析任务 ({tasks.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {tasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                statusConfig={statusConfig}
                allSubjects={allSubjects}
                children={children}
                onSave={() => handleSave(task)}
                onRetry={() => handleRetry(task)}
                onDismiss={() => handleDismiss(task.id)}
                onToggle={() => toggleExpand(task.id)}
                onToggleEdit={() => toggleEditMode(task.id)}
                onRegenerate={() => handleRegenerate(task)}
                onRefine={() => handleRefine(task)}
                onUpdateQuestions={(questions) => updateTaskQuestions(task.id, questions)}
                selected={task.selected}
                onToggleSelect={(i) => toggleQuestionSelection(task.id, i)}
                onUpdateFeedback={(feedback) => updateTaskRefineFeedback(task.id, feedback)}
                onUpdateChild={(child) => updateTaskChild(task.id, child)}
                onUpdateSubject={(subject) => updateTaskSubject(task.id, subject)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/** 任务卡片 */
/** 分析进度条
 *
 * ⚠️ 后端是一次性调用 AI（不流式），拿不到真实进度，所以这里是**按已用时间估算**的：
 * 用 1 - e^(-t/15) 的缓动曲线（前快后慢），并封顶在 95% ——
 * 避免出现"卡在 99%"的观感。它的作用只是让用户知道"确实在跑"。
 *
 * 起点取组件挂载时刻而不是后端的 created_at：后者的时区处理容易出偏差，
 * 而任务本来就只存在于当前页面的内存里，刷新即消失，用本地时间足够。
 */
function AnalysisProgress() {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const started = Date.now()
    const timer = setInterval(() => setElapsed((Date.now() - started) / 1000), 500)
    return () => clearInterval(timer)
  }, [])

  const pct = Math.min(95, Math.round(100 * (1 - Math.exp(-elapsed / 15))))

  return (
    <div style={{ marginTop: 8 }}>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>
        正在分析… 已用 {Math.round(elapsed)} 秒
      </div>
    </div>
  )
}

function TaskCard({
  task, statusConfig, allSubjects, children,
  onSave, onRetry, onDismiss, onToggle, onToggleEdit,
  onRegenerate, onRefine, onUpdateQuestions, onUpdateFeedback,
  selected, onToggleSelect,
  onUpdateChild, onUpdateSubject,
}: {
  task: Task
  statusConfig: Record<string, { Icon: LucideIcon; color: string; label: string }>
  allSubjects: string[]
  children: Array<{ id: string; name: string; emoji: string; subjects: string[] }>
  onSave: () => void
  onRetry: () => void
  onDismiss: () => void
  onToggle: () => void
  onToggleEdit: () => void
  onRegenerate: () => void
  onRefine: () => void
  onUpdateQuestions: (questions: QuestionAnalysis[]) => void
  selected: Set<number>
  onToggleSelect: (index: number) => void
  onUpdateFeedback: (feedback: string) => void
  onUpdateChild: (child: string) => void
  onUpdateSubject: (subject: string) => void
}) {
  const cfg = statusConfig[task.status]
  const time = new Date(task.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  return (
    <div style={{
      background: 'var(--color-surface)',
      borderRadius: 'var(--radius-md)',
      border: `1px solid ${task.status === 'processing' ? '#3b82f640' : 'var(--color-border)'}`,
      boxShadow: 'var(--shadow-sm)',
      overflow: 'hidden',
    }}>
      {/* 任务头部 */}
      <div
        onClick={task.status === 'completed' ? onToggle : undefined}
        style={{
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          cursor: task.status === 'completed' ? 'pointer' : 'default',
        }}
      >
        <cfg.Icon
          size={20}
          color={cfg.color}
          className={task.status === 'processing' ? 'icon-spin' : undefined}
        />
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '14px' }}>
              {children.find(child => child.id === task.child_id)?.emoji} {children.find(child => child.id === task.child_id)?.name} · {task.subject}
            </strong>
            <span style={{
              fontSize: '12px',
              padding: '2px 8px',
              borderRadius: '12px',
              background: cfg.color + '18',
              color: cfg.color,
            }}>
              {cfg.label}
            </span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
            {time} · {task.imageFiles.length} 张图片
          </div>
          {/* 进度条只在真正分析中显示 —— 串行执行时后面的任务会长时间处于
              「等待中」，那时计时器还没意义（它还没开始跑） */}
          {task.status === 'processing' && <AnalysisProgress />}
        </div>

        {/* 操作按钮 */}
        {task.status === 'completed' && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={(e) => { e.stopPropagation(); onSave() }}
              disabled={selected.size === 0}
              style={{
                padding: '6px 16px',
                background: 'var(--color-success)',
                color: '#fff',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              <Save size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
              {selected.size > 0 ? `保存 ${selected.size} 道` : '保存'}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss() }}
              style={{
                padding: '6px 12px',
                background: 'transparent',
                color: 'var(--color-text-secondary)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              忽略
            </button>
          </div>
        )}
        {task.status === 'failed' && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={(e) => { e.stopPropagation(); onRetry() }}
              style={{
                padding: '6px 16px',
                background: 'var(--color-primary)',
                color: '#fff',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              <RotateCw size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
              重试
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss() }}
              style={{
                padding: '6px 12px',
                background: 'transparent',
                color: 'var(--color-text-secondary)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              忽略
            </button>
          </div>
        )}
        {task.status === 'processing' && (
          <div style={{ fontSize: '13px', color: '#3b82f6' }}>AI 分析中...</div>
        )}
      </div>

      {/* 展开的结果 */}
      {task.status === 'completed' && task.expanded && task.result && (
        <div style={{
          padding: '16px',
          borderTop: '1px solid var(--color-border)',
          // 展开区的底色。原来写死 #fafafa（接近白），在深色主题下
          // 会与白色正文撞成「白底白字」，分析结果整个看不见。
          background: 'var(--color-surface-2)',
        }}>
          {/* 孩子/学科选择器 */}
          <div style={{
            display: 'flex',
            gap: '12px',
            marginBottom: '16px',
            padding: '12px',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--color-border)',
          }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
                归属孩子
              </label>
              <select
                value={task.child_id}
                onChange={e => onUpdateChild(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                {children.map(child => (
                  <option key={child.id} value={child.id}>{child.emoji} {child.name}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
                学科
              </label>
              <select
                value={task.subject}
                onChange={e => onUpdateSubject(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                {/* 显示选中孩子的所有学科 */}
                {(children.find(child => child.id === task.child_id)?.subjects || allSubjects).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 操作按钮栏 */}
          <div style={{
            display: 'flex',
            gap: '8px',
            marginBottom: '16px',
            flexWrap: 'wrap',
          }}>
            <button
              onClick={onToggleEdit}
              style={{
                padding: '6px 14px',
                background: task.editMode ? 'var(--color-primary)' : 'transparent',
                color: task.editMode ? '#fff' : 'var(--color-primary)',
                border: '1px solid var(--color-primary)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              <Pencil size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
              {task.editMode ? '完成编辑' : '编辑'}
            </button>
            <button
              onClick={onRegenerate}
              style={{
                padding: '6px 14px',
                background: 'transparent',
                color: 'var(--color-warning)',
                border: '1px solid var(--color-warning)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              <RefreshCw size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
              重新生成
            </button>
          </div>

          {/* 分析结果预览 */}
          <AnalysisPreview
            result={task.result}
            selected={selected}
            onToggleSelect={onToggleSelect}
            editable={task.editMode}
            onChange={onUpdateQuestions}
          />

          {/* 反馈优化区域 */}
          <div style={{
            marginTop: '16px',
            padding: '12px',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--color-border)',
          }}>
            <label style={{ fontSize: '13px', fontWeight: 500, display: 'block', marginBottom: '8px' }}>
              💬 给 AI 反馈（可选）
            </label>
            <textarea
              value={task.refineFeedback}
              onChange={e => onUpdateFeedback(e.target.value)}
              placeholder="例如：这个错误类型应该是审题错误而不是计算错误；请补充更详细的解题步骤..."
              rows={2}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                fontSize: '13px',
                resize: 'vertical',
              }}
            />
            <button
              onClick={onRefine}
              disabled={!task.refineFeedback.trim()}
              style={{
                marginTop: '8px',
                padding: '6px 16px',
                background: 'var(--color-primary)',
                color: '#fff',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
              }}
            >
              🚀 根据反馈优化
            </button>
          </div>
        </div>
      )}

      {/* 错误信息 */}
      {task.status === 'failed' && task.error && (
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--color-border)',
          background: 'var(--color-error-light)',
          color: 'var(--color-error)',
          fontSize: '13px',
        }}>
          错误: {task.error}
        </div>
      )}
    </div>
  )
}
