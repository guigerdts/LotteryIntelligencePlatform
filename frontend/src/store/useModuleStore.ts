import { create } from "zustand";

interface ModuleState {
  /** Sidebar collapsed state. */
  sidebarCollapsed: boolean;
  /** Toggle sidebar collapsed state. */
  toggleSidebar: () => void;
  /** Set sidebar collapsed state. */
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useModuleStore = create<ModuleState>()((set) => ({
  sidebarCollapsed: false,

  toggleSidebar: () => {
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
  },

  setSidebarCollapsed: (collapsed) => {
    set({ sidebarCollapsed: collapsed });
  },
}));
