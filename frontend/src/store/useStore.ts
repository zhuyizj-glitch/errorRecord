/** 全局状态管理 */

import { create } from 'zustand'
import { fetchChildren as apiFetchChildren } from '../api/client'
import type { Child } from '../types'

interface AppState {
  children: Child[]
  availableSubjects: string[]
  currentChild: string | null
  currentSubject: string | null
  setChild: (child: string) => void
  setSubject: (subject: string) => void
  fetchChildren: () => Promise<void>
}

export const useStore = create<AppState>((set, get) => ({
  children: [],
  availableSubjects: [],
  currentChild: null,
  currentSubject: null,

  setChild: (child: string) => {
    set({ currentChild: child, currentSubject: null })
  },

  setSubject: (subject: string) => {
    set({ currentSubject: subject })
  },

  fetchChildren: async () => {
    try {
      const data = await apiFetchChildren()
      set({ children: data.children, availableSubjects: data.available_subjects })
      // 默认选第一个孩子
      const ids = data.children.map((child: Child) => child.id)
      if (ids.length > 0 && !ids.includes(get().currentChild || '')) {
        set({ currentChild: ids[0], currentSubject: data.children[0].subjects[0] || null })
      }
    } catch (e) {
      console.error('获取孩子列表失败:', e)
    }
  },
}))
