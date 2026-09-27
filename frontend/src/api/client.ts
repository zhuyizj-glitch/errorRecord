/** API 客户端 */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  withCredentials: true,
})

export const authStatus = () => api.get('/auth/status').then(r => r.data)
export const initializeAccount = (data: unknown) => api.post('/auth/initialize', data).then(r => r.data)
export const login = (data: unknown) => api.post('/auth/login', data).then(r => r.data)
export const register = (data: unknown) => api.post('/auth/register', data).then(r => r.data)
export const logout = () => api.post('/auth/logout')
export const fetchMe = () => api.get('/auth/me').then(r => r.data)
export const changePassword = (data: unknown) => api.post('/auth/change-password', data).then(r => r.data)

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
export const fetchQuestions = (childId: string, subject?: string) =>
  api.get('/questions', { params: { child_id: childId, subject } }).then(r => r.data)

export const createQuestion = (data: any) =>
  api.post('/questions', data).then(r => r.data)

// 复习
export const fetchReviewPlan = (childId: string) =>
  api.get('/review/plan', { params: { child_id: childId } }).then(r => r.data)

export const createChild = (data: unknown) => api.post('/children', data).then(r => r.data)
export const updateChild = (id: string, data: unknown) => api.patch(`/children/${id}`, data).then(r => r.data)
export const fetchInvites = () => api.get('/admin/invites').then(r => r.data)
export const createInvite = (expiresInDays = 7) => api.post('/admin/invites', { expires_in_days: expiresInDays }).then(r => r.data)
export const revokeInvite = (id: string) => api.delete(`/admin/invites/${id}`)
export const fetchAccounts = () => api.get('/admin/accounts').then(r => r.data)
export const resetAccountPassword = (id: string) => api.post(`/admin/accounts/${id}/reset-password`).then(r => r.data)

// 设置
export const fetchSettings = () => api.get('/settings').then(r => r.data)
export const saveSettings = (data: any) => api.put('/settings', data).then(r => r.data)
export const testConnection = (data: any) => api.post('/settings/test', data).then(r => r.data)

export default api
