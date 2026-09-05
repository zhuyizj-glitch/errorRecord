/** API 客户端 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 孩子
export const fetchChildren = () => api.get('/children').then(r => r.data)

// 上传
export const uploadImages = (files: File[]) => {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  return api.post('/upload/images', form).then(r => r.data)
}

// 分析
export const analyzeImages = (imageIds: any[]) =>
  api.post('/analyze', imageIds).then(r => r.data)

// 错题
export const fetchQuestions = (child: string, subject?: string) =>
  api.get('/questions', { params: { child, subject } }).then(r => r.data)

export const createQuestion = (data: any) =>
  api.post('/questions', data).then(r => r.data)

export const deleteQuestion = (id: string, child: string, subject: string) =>
  api.delete(`/questions/${id}`, { params: { child, subject } }).then(r => r.data)

// 复习
export const fetchReviewPlan = (child: string) =>
  api.get('/review/plan', { params: { child } }).then(r => r.data)

// 设置
export const fetchSettings = () => api.get('/settings').then(r => r.data)
export const saveSettings = (data: any) => api.put('/settings', data).then(r => r.data)
export const testConnection = (data: any) => api.post('/settings/test', data).then(r => r.data)

export default api
