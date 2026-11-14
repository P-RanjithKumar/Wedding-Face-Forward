"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
    Cpu,
    Clock,
    CheckCircle,
    AlertTriangle,
    ImageIcon,
    Zap,
    BarChart3,
    HardDrive,
} from "lucide-react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from "recharts";
import { fetchStats, fetchSettings, fetchWorkerStatus, WS_BASE } from "@/lib/api";
import { useSystemStore } from "@/lib/store";
import { WorkerPanel } from "@/components/processing/worker-panel";
import { DataFlowPipeline } from "@/components/processing/data-flow-pipeline";

const STATUS_COLORS: Record<string, string> = {
    pending: "#f59e0b",
    processing: "#06B6D4",
    completed: "#22C55E",
    error: "#EF4444",
    no_faces: "#8B5CF6",
};

const STATUS_ICONS: Record<string, typeof Cpu> = {
    pending: Clock,
    processing: Zap,
    completed: CheckCircle,
    error: AlertTriangle,
    no_faces: ImageIcon,
};

export default function ProcessingPage() {
    const setPageTitle = useSystemStore((s) => s.setPageTitle);
    const [isScrolled, setIsScrolled] = useState(false);
    const [liveData, setLiveData] = useState<{
        stats?: any;
        progress?: any;
        workers?: Record<string, string>;
    }>({});

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setIsScrolled(e.currentTarget.scrollTop > 5);
    };

    useEffect(() => { setPageTitle("Processing"); }, [setPageTitle]);

    // ── WebSocket for real-time status ──────────────────────────────────────
    useEffect(() => {
        const wsUrl = `${WS_BASE}/process-status`;
        let ws: WebSocket | null = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setLiveData(data);
            } catch (err) {
                console.error("Failed to parse process status:", err);
            }
        };

        const heartbeat = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send("ping");
            }
        }, 10000);

        return () => {
            clearInterval(heartbeat);
            ws?.close();
            ws = null;
        };
    }, []);

    const { data: settings } = useQuery({
        queryKey: ["admin-settings"],
        queryFn: fetchSettings,
    });

    const { data: workerStatus } = useQuery({
        queryKey: ["worker-status"],
        queryFn: fetchWorkerStatus,
        refetchInterval: 5000,
    });

    const stats = liveData.stats;
    const workerStates = liveData.workers || {};
    const workerCount = settings?.WORKER_COUNT ? parseInt(settings.WORKER_COUNT, 10) : 4;
    const isEngineRunning = workerStatus?.is_running ?? false;

    const photosByStatus = stats?.photos_by_status ?? {};
    const totalPhotos = stats?.total_photos ?? 0;
    const processedCount = photosByStatus["completed"] ?? 0;
    const pendingCount = photosByStatus["pending"] ?? 0;
    const errorCount = photosByStatus["error"] ?? 0;
    const processingCount = photosByStatus["processing"] ?? 0;
    const processedPct =
        totalPhotos > 0 ? Math.round((processedCount / totalPhotos) * 100) : 0;

    const chartData = Object.keys(STATUS_COLORS).map((status) => ({
        name:
            status.charAt(0).toUpperCase() +
            status.slice(1).replace("_", " "),
        count: photosByStatus[status] ?? 0,
        color: STATUS_COLORS[status],
    }));

    const processingStates = Object.fromEntries(
        Object.entries(workerStates).filter(([key]) => !key.includes("Uploader"))
    );
    
    const uploadStates = Object.fromEntries(
        Object.entries(workerStates).filter(([key]) => key.includes("Uploader"))
    );

    return (
        <div className="flex flex-col gap-4 h-full animate-fade-in w-full overflow-y-auto pb-10 scrollbar-hide">
            {/* Top row with metrics and charts */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full shrink-0">
                {/* Metrics */}
                <div className="flex flex-col gap-6">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        <MetricCard label="Total Photos" value={totalPhotos} icon={HardDrive} color="var(--accent-cyan)" delay={0} />
                        <MetricCard label="Processed" value={`${processedPct}%`} icon={CheckCircle} color="var(--accent-primary)" delay={0.05} />
                        <MetricCard label="Pending" value={pendingCount} icon={Clock} color="var(--accent-amber)" delay={0.1} />
                        <MetricCard label="Errors" value={errorCount} icon={AlertTriangle} color="var(--accent-rose)" delay={0.15} />
                    </div>

                    {/* Breakdown */}
                    <motion.div
                        className="card-base p-5 h-full"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                    >
                        <h3
                            className="text-[11px] font-semibold uppercase tracking-widest mb-3"
                            style={{ color: "var(--text-tertiary)" }}
                        >
                            Breakdown
                        </h3>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                            {Object.entries(photosByStatus).map(([status, count]) => {
                                const Icon = STATUS_ICONS[status] || Cpu;
                                const color = STATUS_COLORS[status] || "#71717A";
                                return (
                                    <div
                                        key={status}
                                        className="flex items-center gap-3 p-3 rounded-lg"
                                        style={{ background: "var(--bg-inner)" }}
                                    >
                                        <Icon size={15} style={{ color }} />
                                        <div>
                                            <p
                                                className="text-base font-bold tabular-nums"
                                                style={{
                                                    fontFamily:
                                                        "var(--font-jakarta)",
                                                }}
                                            >
                                                {count as React.ReactNode}
                                            </p>
                                            <p
                                                className="text-[9px] uppercase tracking-wider"
                                                style={{ color: "var(--text-muted)" }}
                                            >
                                                {status.replace("_", " ")}
                                            </p>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </motion.div>
                </div>

                {/* Bar chart */}
                <motion.div
                    className="card-base p-5 flex flex-col"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25 }}
                >
                    <div className="flex items-center gap-2 mb-4">
                        <BarChart3 size={15} style={{ color: "var(--accent-violet)" }} fill="currentColor" />
                        <h3
                            className="text-[11px] font-semibold uppercase tracking-widest"
                            style={{ color: "var(--text-tertiary)" }}
                        >
                            Photos by Status
                        </h3>
                    </div>

                    {chartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200} className="flex-1">
                            <BarChart data={chartData} barCategoryGap="20%">
                                <XAxis
                                    dataKey="name"
                                    tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <YAxis
                                    tick={{
                                        fill: "var(--text-muted)",
                                        fontSize: 11,
                                        fontFamily: "var(--font-mono)",
                                    }}
                                    axisLine={false}
                                    tickLine={false}
                                />
                                <Tooltip
                                    contentStyle={{
                                        background: "var(--bg-card)",
                                        border: "none",
                                        borderRadius: 8,
                                        color: "var(--text-primary)",
                                        fontSize: 12,
                                        boxShadow: "var(--shadow-lg)",
                                    }}
                                />
                                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                    {chartData.map((entry, i) => (
                                        <Cell key={i} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <p
                            className="text-[12px] text-center py-8 flex-1 flex items-center justify-center"
                            style={{ color: "var(--text-muted)" }}
                        >
                            No processing data yet
                        </p>
                    )}
                </motion.div>
            </div>

            {/* Bottom Section: Cinematic Pipeline Visualization */}
            <div className="w-full flex-1 min-h-[300px] relative rounded-2xl overflow-hidden shadow-2xl border border-white/5 bg-black/40 backdrop-blur-sm">
                <DataFlowPipeline 
                    isEngineRunning={isEngineRunning}
                    workerCount={workerCount} 
                    processingStates={processingStates}
                    uploadStates={uploadStates}
                    stats={stats}
                />
            </div>
        </div>
    );
}

function MetricCard({
    label,
    value,
    icon: Icon,
    color,
    delay,
}: {
    label: string;
    value: number | string;
    icon: typeof Cpu;
    color: string;
    delay: number;
}) {
    return (
        <motion.div
            className="card-base p-4 relative overflow-hidden"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay }}
        >
            <div
                className="w-8 h-8 rounded-lg flex items-center justify-center mb-2.5"
                style={{ background: "var(--bg-elevated)", color }}
            >
                <Icon size={16} strokeWidth={1.5} fill="currentColor" />
            </div>
            <p
                className="text-xl font-bold"
                style={{ fontFamily: "var(--font-jakarta)" }}
            >
                {typeof value === "number" ? value.toLocaleString() : value}
            </p>
            <p
                className="text-[10px] mt-0.5 uppercase tracking-wider"
                style={{ color: "var(--text-muted)" }}
            >
                {label}
            </p>
        </motion.div>
    );
}
