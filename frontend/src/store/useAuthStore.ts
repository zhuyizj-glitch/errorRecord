import { create } from 'zustand'
import { authStatus, fetchMe } from '../api/client'
import type { Account } from '../types'

interface AuthState {
  loading: boolean
  initialized: boolean | null
  account: Account | null
  refresh: () => Promise<void>
  clear: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  loading: true,
  initialized: null,
  account: null,
  refresh: async () => {
    set({ loading: true })
    const status = await authStatus()
    if (!status.initialized) {
      set({ loading: false, initialized: false, account: null })
      return
    }
    try {
      const account = await fetchMe()
      set({ loading: false, initialized: true, account })
    } catch {
      set({ loading: false, initialized: true, account: null })
    }
  },
  clear: () => set({ account: null }),
}))
