"use client";

import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { TrendingUp } from "lucide-react";

interface StatCardProps {
    label: string;
    value: number | string;
    icon: LucideIcon;
    accentColor: string;
    glowColor: string;
    delay?: number;
    trend?: string;
}

export function StatCard({
    label,
    value,
    icon: Icon,
    accentColor,
    glowColor,
    delay = 0,
    trend,
}: StatCardProps) {
    return (
        <motion.div
            className="card-base relative overflow-hidden p-4 flex flex-col gap-2.5 cursor-pointer"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay, ease: [0.4, 0, 0.2, 1] }}
            whileHover={{ y: -2 }}
        >


            {/* Header: Icon + Trend */}
            <div className="flex items-center justify-between relative z-10">
                <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{
                        background: "var(--bg-elevated)",
                        color: "var(--text-primary)",
                    }}
                >
                    <Icon size={18} strokeWidth={1.5} fill="currentColor" />
                </div>
                {trend && (
                    <span
                        className="flex items-center gap-1 text-[10px] font-semibold"
                        style={{ color: accentColor }}
                    >
                        <TrendingUp size={10} />
                        {trend}
                    </span>
                )}
            </div>

            {/* Value & Label */}
            <div className="relative z-10">
                <motion.p
                    className="text-2xl font-bold tracking-tight"
                    style={{
                        fontFamily: "var(--font-jakarta)",
                        color: "var(--text-primary)",
                    }}
                    key={String(value)}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                >
                    {typeof value === "number" ? value.toLocaleString() : value}
                </motion.p>
                <p
                    className="text-[11px] mt-0.5 font-medium uppercase tracking-wider"
                    style={{ color: "var(--text-muted)" }}
                >
                    {label}
                </p>
            </div>
        </motion.div>
    );
}
