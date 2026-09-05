/** 全局状态管理 */

import { create } from 'zustand'
import { fetchChildren as apiFetchChildren } from '../api/client'
import type { ChildrenMap } from '../types'

interface AppState {
  children: ChildrenMap
  currentChild: string | null
  currentSubject: string | null
  setChild: (child: string) => void
  setSubject: (subject: string) => void
  fetchChildren: () => Promise<void>
}

export const useStore = create<AppState>((set, get) => ({
  children: {},
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
      set({ children: data })
      // 默认选第一个孩子
      const keys = Object.keys(data)
      if (keys.length > 0 && !get().currentChild) {
        set({ currentChild: keys[0] })
      }
    } catch (e) {
      console.error('获取孩子列表失败:', e)
    }
  },
}))
