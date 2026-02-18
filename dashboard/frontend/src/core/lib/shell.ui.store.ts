// ©AngelaMos | 2026
// shell.ui.store.ts

import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface UIState {
  sidebarOpen: boolean
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  toggleSidebarCollapsed: () => void
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        sidebarOpen: false,
        sidebarCollapsed: false,

        toggleSidebar: () =>
          set(
            (state) => ({ sidebarOpen: !state.sidebarOpen }),
            false,
            'ui/toggleSidebar'
          ),

        setSidebarOpen: (open) =>
          set({ sidebarOpen: open }, false, 'ui/setSidebarOpen'),

        toggleSidebarCollapsed: () =>
          set(
            (state) => ({ sidebarCollapsed: !state.sidebarCollapsed }),
            false,
            'ui/toggleSidebarCollapsed'
          ),
      }),
      {
        name: 'codeworm-ui',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      }
    ),
    { name: 'UIStore' }
  )
)
