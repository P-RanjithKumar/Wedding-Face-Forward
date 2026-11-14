"use client";

import { motion } from "framer-motion";
import { Cpu, Clock, AlertTriangle, CheckCircle } from "lucide-react";
import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
} from "recharts";
import type { StatsResponse } from "@/lib/api";

interface ProcessingWidgetProps {
    stats: StatsResponse | undefined;
    isLoading: boolean;
}

const STATUS_COLORS: Record<string, string> = {
    pending: "#eab308",
    processing: "#0ea5e9",
    completed: "#10b981",
    processed: "#10b981",
    error: "#f43f5e",
    no_faces: "#6366f1",
};

const STATUS_LABELS: Record<string, string> = {
    pending: "Pending",
    processing: "In Progress",
    completed: "Complete",
    processed: "Complete",
    error: "Errors",
    no_faces: "No Faces",
};

export function ProcessingWidget({ stats, isLoading }: ProcessingWidgetProps) {
    const photosByStatus = stats?.photos_by_status ?? {};
    const totalPhotos = stats?.total_photos ?? 0;

    const chartData = Object.entries(photosByStatus)
        .filter(([, count]) => count > 0)
        .map(([status, count]) => ({
            name: STATUS_LABELS[status] || status,
            value: count,
            color: STATUS_COLORS[status] || "#71717A",
        }));

    const processing = (photosByStatus["processing"] ?? 0) > 0;
    const hasErrors = (photosByStatus["error"] ?? 0) > 0;

    return (
        <motion.div
            className="card-base p-5 flex flex-col justify-start"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            style={{ minHeight: 420 }}
        >
            <div className="flex items-center gap-2 mb-4">
                <Cpu size={16} style={{ color: "var(--text-tertiary)" }} />
                <h3
                    className="text-[11px] font-semibold uppercase tracking-widest"
                    style={{ color: "var(--text-tertiary)" }}
                >
                    Processing Pipeline
                </h3>
                <div className="ml-auto">
                    {processing ? (
                        <span
                            className="badge badge-info"
                        >
                            <Clock size={10} /> Active
                        </span>
                    ) : hasErrors ? (
                        <span
                            className="badge badge-danger"
                        >
                            <AlertTriangle size={10} /> Errors
                        </span>
                    ) : (
                        <span
                            className="badge badge-success"
                        >
                            <CheckCircle size={10} /> Idle
                        </span>
                    )}
                </div>
            </div>

            <div className="flex flex-col items-center justify-center gap-4 mt-2 flex-1">
                {/* 
                  To prevent the pie chart from being cutoff, we ensure 
                  the width and height give it enough breathing room. 
                */}
                <div className="w-72 h-72 sm:w-88 sm:h-88 relative shrink-0">
                    {isLoading || chartData.length === 0 ? (
                        <div
                            className="w-full h-full rounded-full flex items-center justify-center"
                            style={{ border: "none" }}
                        >
                            <span
                                className="text-xs font-medium"
                                style={{ color: "var(--text-muted)" }}
                            >
                                {isLoading ? "..." : "No data"}
                            </span>
                        </div>
                    ) : (
                        <div className="w-full h-full overflow-hidden flex items-center justify-center">
                            <ResponsiveContainer width={340} height={340}>
                                <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                                    <Pie
                                        data={chartData}
                                        innerRadius={105}
                                        outerRadius={140}
                                        paddingAngle={3}
                                        dataKey="value"
                                        strokeWidth={0}
                                        cx="50%"
                                        cy="50%"
                                    >
                                        {chartData.map((entry, idx) => (
                                            <Cell key={idx} fill={entry.color} />
                                        ))}
                                    </Pie>
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <span
                            className="text-4xl sm:text-5xl font-bold"
                            style={{
                                fontFamily: "var(--font-jakarta)",
                                color: "var(--text-primary)",
                                transform: "translateY(4px)"
                            }}
                        >
                            {totalPhotos.toLocaleString()}
                        </span>
                        <span
                            className="text-[10px] font-medium uppercase tracking-widest mt-1 opacity-80"
                            style={{ color: "var(--text-muted)" }}
                        >
                            Items
                        </span>
                    </div>
                </div>

                {/* Legend */}
                <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 w-full mt-2">
                    {chartData.map((item) => (
                        <div
                            key={item.name}
                            className="flex items-center gap-2 text-xs font-medium"
                        >
                            <div
                                className="w-2.5 h-2.5 rounded-sm"
                                style={{ background: item.color }}
                            />
                            <span style={{ color: "var(--text-secondary)" }}>
                                {item.name}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </motion.div>
    );
}
