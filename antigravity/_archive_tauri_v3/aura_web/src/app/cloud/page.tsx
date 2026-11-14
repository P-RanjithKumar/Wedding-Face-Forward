"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
    Cloud,
    Upload,
    CheckCircle,
    Clock,
    BarChart3,
} from "lucide-react";
import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
} from "recharts";
import { fetchStats } from "@/lib/api";
import { useSystemStore } from "@/lib/store";

export default function CloudPage() {
    const setPageTitle = useSystemStore((s) => s.setPageTitle);
    useEffect(() => { setPageTitle("Cloud Sync"); }, [setPageTitle]);

    const { data: stats } = useQuery({
        queryKey: ["stats"],
        queryFn: fetchStats,
        refetchInterval: 5000,
    });

    const processed = stats?.photos_by_status?.completed ?? 0;
    const total = stats?.total_photos ?? 0;
    const pending = stats?.photos_by_status?.pending ?? 0;
    const syncPct = total > 0 ? Math.round((processed / total) * 100) : 0;

    const chartData = [
        { name: "Uploaded", value: processed, color: "#22C55E" },
        { name: "Pending", value: pending, color: "#f59e0b" },
        { name: "Other", value: Math.max(0, total - processed - pending), color: "#8B5CF6" },
    ].filter((d) => d.value > 0);

    return (
        <div className="space-y-4 animate-fade-in" style={{ maxWidth: 960 }}>
            {/* Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <motion.div
                    className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <CheckCircle size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <p className="text-xl font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>
                        {processed.toLocaleString()}
                    </p>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Processed</p>
                </motion.div>

                <motion.div
                    className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 }}
                >
                    
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <Clock size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <p className="text-xl font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>
                        {pending.toLocaleString()}
                    </p>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Pending</p>
                </motion.div>

                <motion.div
                    className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <Upload size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <p className="text-xl font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>
                        {syncPct}%
                    </p>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Sync Progress</p>
                </motion.div>
            </div>

            {/* Donut */}
            <motion.div
                className="card-base p-5"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 }}
            >
                <div className="flex items-center gap-2 mb-4">
                    <BarChart3 size={15} style={{ color: "var(--accent-violet)" }} fill="currentColor" />
                    <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>
                        Cloud Sync Status
                    </h3>
                </div>
                <div className="flex items-center gap-8">
                    <div className="w-36 h-36 relative">
                        {chartData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={chartData} innerRadius={42} outerRadius={64} paddingAngle={3} dataKey="value" strokeWidth={0}>
                                        {chartData.map((e, i) => <Cell key={i} fill={e.color} />)}
                                    </Pie>
                                </PieChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="w-full h-full rounded-full flex items-center justify-center" style={{ border: "none" }}>
                                <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>No data</span>
                            </div>
                        )}
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-lg font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>{syncPct}%</span>
                            <span className="text-[9px]" style={{ color: "var(--text-muted)" }}>Synced</span>
                        </div>
                    </div>
                    <div className="space-y-2.5">
                        {chartData.map((d) => (
                            <div key={d.name} className="flex items-center gap-2 text-[12px]">
                                <div className="w-2 h-2 rounded-sm" style={{ background: d.color }} />
                                <span style={{ color: "var(--text-secondary)" }}>{d.name}</span>
                                <span className="ml-auto font-semibold tabular-nums" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                                    {d.value.toLocaleString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </motion.div>

            {/* Info */}
            <motion.div
                className="card-base p-5"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
            >
                <div className="flex items-center gap-2 mb-3">
                    <Cloud size={15} style={{ color: "var(--accent-primary)" }} fill="currentColor" />
                    <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>
                        Google Drive Integration
                    </h3>
                </div>
                <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    Photos are automatically uploaded to Google Drive after processing. Configure your Drive Folder ID and credentials in Settings. The upload queue runs in the background and retries failed uploads automatically.
                </p>
            </motion.div>
        </div>
    );
}
