// ============================================================
// AURA — Zustand Stores
// Global client state for system status and UI preferences
// ============================================================

import { create } from "zustand";

interface SystemState {
    /** Whether the backend server is reachable */
    serverOnline: boolean;
    setServerOnline: (online: boolean) => void;

    /** Whether the sidebar is collapsed */
    sidebarCollapsed: boolean;
    toggleSidebar: () => void;

    /** Current page title for the header */
    pageTitle: string;
    setPageTitle: (title: string) => void;

    /** Theme mode */
    theme: "light" | "dark";
    setTheme: (theme: "light" | "dark") => void;

    /** Background Gradient Mood */
    gradientMood: string;
    setGradientMood: (mood: string) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
    serverOnline: false,
    setServerOnline: (online) => set({ serverOnline: online }),

    sidebarCollapsed: false,
    toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

    pageTitle: "Dashboard",
    setPageTitle: (title) => set({ pageTitle: title }),

    theme: "light",
    setTheme: (theme) => set({ theme }),

    gradientMood: "graphite",
    setGradientMood: (mood) => set({ gradientMood: mood }),
}));
