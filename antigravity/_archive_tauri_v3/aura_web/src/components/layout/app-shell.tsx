"use client";

import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { useSystemStore } from "@/lib/store";
import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
    const theme = useSystemStore((s) => s.theme);

    return (
        <div className={`flex min-h-screen dashboard-theme ${theme === "dark" ? "dark" : ""}`}>
            <Sidebar />

            <main className="flex-1 h-screen flex flex-col overflow-hidden relative">
                {/* Premium Acrylic/Mica Backdrop */}
                <div className="acrylic-surface ml-[80px]" />

                <div className="relative z-30">
                    <Header />
                </div>
                <div className="flex-1 relative z-10 w-full flex flex-col min-h-0 pl-[80px]">
                    <div className="flex-1 p-8 pt-4 flex flex-col min-h-0 overflow-visible">
                        {children}
                    </div>
                </div>
            </main>
        </div>
    );
}
