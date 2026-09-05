/** 上传错题页面 - 异步任务列表模式 */

import { useState, useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import ImageUploader from '../components/ImageUploader'
import AnalysisPreview from '../components/AnalysisPreview'
import { createQuestion } from '../api/client'
import type { AnalyzeResult } from '../types'

interface Task {
  id: string
  child: string
  subject: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  result: AnalyzeResult | null
  error: string | null
  created_at: string
  completed_at: string | null
  expanded: boolean
  imageFiles: File[]
  editMode: boolean
  refineFeedback: string
}

export default function UploadPage() {
  const { currentChild, currentSubject, children } = useStore()
  const [files, setFiles] = useState<File[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [error, setError] = useState('')

  // 获取所有学科列表
  const allSubjects = currentChild && children[currentChild]
    ? children[currentChild].subjects
    : []

  // 轮询任务状态 - 使用 ref 避免闭包问题
  const tasksRef = useRef(tasks)
  tasksRef.current = tasks

  useEffect(() => {
    const poll = async () => {
      const currentTasks = tasksRef.current
      const pendingTasks = currentTasks.filter(t => t.status === 'pending' || t.status === 'processing')

      for (const task of pendingTasks) {
        try {
          const res = await fetch(`/api/tasks/${task.id}`).then(r => r.json())
          if (res.status !== task.status || JSON.stringify(res.result) !== JSON.stringify(task.result)) {
            setTasks(prev => prev.map(t =>
              t.id === task.id
                ? { ...t, status: res.status, result: res.result, error: res.error, completed_at: res.completed_at }
                : t
            ))
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

    try {
      // 1. 上传图片
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      const uploadRes = await fetch('/api/upload/images', { method: 'POST', body: form }).then(r => r.json())

      if (!uploadRes.image_ids?.length) {
        setError('上传失败')
        return
      }

      // 2. 创建异步任务
      const taskRes = await fetch(`/api/tasks?child=${currentChild}&subject=${encodeURIComponent(currentSubject)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          child: currentChild,
          subject: currentSubject,
          image_ids: uploadRes.image_ids,
        }),
      }).then(r => r.json())

      // 3. 添加到任务列表
      const newTask: Task = {
        id: taskRes.task_id,
        child: currentChild,
        subject: currentSubject,
        status: 'pending',
        result: null,
        error: null,
        created_at: taskRes.created_at,
        completed_at: null,
        expanded: true,
        imageFiles: files,
        editMode: false,
        refineFeedback: '',
      }

      setTasks(prev => [newTask, ...prev])
      setFiles([])

    } catch (e: any) {
      setError('创建任务失败: ' + (e.message || e))
    }
  }

  const handleSave = async (task: Task) => {
    if (!task.result) return
    try {
      await createQuestion({
        child: task.child,
        subject: task.subject,
        topic: task.result.metadata.topic,
        error_type: task.result.error_analysis?.error_type || null,
        source_type: task.result.source_type,
        difficulty: task.result.metadata.difficulty,
        error_date: new Date().toISOString().split('T')[0],
        question_text: task.result.question_text,
        correct_answer: task.result.correct_answer,
        solution_steps: task.result.solution_steps,
        error_analysis: task.result.error_analysis,
        error_suggestion: task.result.error_analysis?.suggestion,
        knowledge_points: task.result.metadata.knowledge_points,
        tags: ['错题'],
        image_ids: task.imageFiles.map(f => f.name),
      })
      setTasks(prev => prev.filter(t => t.id !== task.id))
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
      const uploadRes = await fetch('/api/upload/images', { method: 'POST', body: form }).then(r => r.json())

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

  const updateTaskResult = (taskId: string, result: AnalyzeResult) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, result } : t))
  }

  const updateTaskRefineFeedback = (taskId: string, feedback: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, refineFeedback: feedback } : t))
  }

  const updateTaskChild = (taskId: string, child: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, child } : t))
  }

  const updateTaskSubject = (taskId: string, subject: string) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, subject } : t))
  }

  const statusConfig = {
    pending: { icon: '⏳', color: '#94a3b8', label: '等待中' },
    processing: { icon: '🔄', color: '#3b82f6', label: '分析中' },
    completed: { icon: '✅', color: '#10b981', label: '完成' },
    failed: { icon: '❌', color: '#ef4444', label: '失败' },
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
          {currentChild === 'daughter' ? '👧 女儿' : '👦 儿子'} · {currentSubject}
        </span>
      </div>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: '20px', fontSize: '14px' }}>
        上传后会自动开始 AI 分析，你可以继续上传其他题目
      </p>

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
            disabled={!files.length}
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
            🔍 开始分析
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
          background: '#fff3f3',
          border: '1px solid #ffcdd2',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-error)',
          fontSize: '14px',
        }}>
          {error}
        </div>
      )}

      {/* 任务列表 */}
      {tasks.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>
            📋 分析任务 ({tasks.length})
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
                onUpdateResult={(result) => updateTaskResult(task.id, result)}
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
function TaskCard({
  task, statusConfig, allSubjects, children,
  onSave, onRetry, onDismiss, onToggle, onToggleEdit,
  onRegenerate, onRefine, onUpdateResult, onUpdateFeedback,
  onUpdateChild, onUpdateSubject,
}: {
  task: Task
  statusConfig: Record<string, { icon: string; color: string; label: string }>
  allSubjects: string[]
  children: Record<string, { name: string; emoji: string; subjects: string[] }>
  onSave: () => void
  onRetry: () => void
  onDismiss: () => void
  onToggle: () => void
  onToggleEdit: () => void
  onRegenerate: () => void
  onRefine: () => void
  onUpdateResult: (result: AnalyzeResult) => void
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
        <span style={{ fontSize: '20px' }}>{cfg.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '14px' }}>
              {task.child === 'daughter' ? '👧 女儿' : '👦 儿子'} · {task.subject}
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
        </div>

        {/* 操作按钮 */}
        {task.status === 'completed' && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={(e) => { e.stopPropagation(); onSave() }}
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
              💾 保存
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
              🔄 重试
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
          background: '#fafafa',
        }}>
          {/* 孩子/学科选择器 */}
          <div style={{
            display: 'flex',
            gap: '12px',
            marginBottom: '16px',
            padding: '12px',
            background: '#fff',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--color-border)',
          }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
                归属孩子
              </label>
              <select
                value={task.child}
                onChange={e => onUpdateChild(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)',
                  fontSize: '13px',
                }}
              >
                {Object.entries(children).map(([key, child]) => (
                  <option key={key} value={key}>{child.emoji} {child.name}</option>
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
                {(children[task.child]?.subjects || allSubjects).map(s => (
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
              ✏️ {task.editMode ? '完成编辑' : '编辑'}
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
              🔄 重新生成
            </button>
          </div>

          {/* 分析结果预览 */}
          <AnalysisPreview
            result={task.result}
            editable={task.editMode}
            onChange={onUpdateResult}
          />

          {/* 反馈优化区域 */}
          <div style={{
            marginTop: '16px',
            padding: '12px',
            background: '#fff',
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
          background: '#fff3f3',
          color: 'var(--color-error)',
          fontSize: '13px',
        }}>
          错误: {task.error}
        </div>
      )}
    </div>
  )
}
