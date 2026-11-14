"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Camera,
  Users,
  UserCheck,
  Scan,
  Image as ImageIcon,
  ArrowUpRight,
  CheckCircle,
  Wifi,
} from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { ActivityLog } from "@/components/dashboard/activity-log";
import { ProcessingWidget } from "@/components/dashboard/processing-widget";
import { fetchStats, type StatsResponse } from "@/lib/api";
import { useSystemStore } from "@/lib/store";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

export default function DashboardPage() {
    const theme = useSystemStore((s) => s.theme);
    const { data: stats } = useQuery<StatsResponse>({
        queryKey: ["stats"],
        queryFn: fetchStats,
        refetchInterval: 5_000,
    });

    const photosByStatus = stats?.photos_by_status ?? {};
    
    // Process data for the chart
    const STATUS_COLORS: Record<string, string> = {
        completed: "#5EBF9E",
        processed: "#5EBF9E", // Add processed
        processing: "#4BA8FF",
        pending: "#FDE285",
        error: "#E87461",
        no_faces: "#8B5CF6", // Add no_faces
    };

    const chartData = Object.entries(photosByStatus)
        .filter(([status, count]) => count > 0 && STATUS_COLORS[status])
        .map(([status, count]) => ({
            name: status,
            value: count,
            color: STATUS_COLORS[status],
        }));

    const hasData = chartData.length > 0;
    
    return (
        <div className="grid grid-cols-12 gap-6 h-full min-h-0">
            {/* Left Column: Stats & Analytics */}
            <div className="col-span-12 xl:col-span-7 flex flex-col gap-6">
                
                {/* 2x2 Stats Card */}
                <div className="dash-card p-6 h-auto xl:h-[280px] flex flex-col">
                    <div className="grid grid-cols-1 sm:grid-cols-2 flex-1 relative">
                        {/* Horizontal Divider (Desktop Only) */}
                        <div className="hidden sm:block absolute top-1/2 left-0 w-full h-px border-t border-dashed border-muted/20 -translate-y-1/2" />
                        {/* Vertical Divider (Desktop Only) */}
                        <div className="hidden sm:block absolute top-0 left-1/2 h-full w-px border-l border-dashed border-muted/20 -translate-x-1/2" />
                        {/* Top Left: Total Photos */}
                        <div className="flex items-center justify-between p-4 flex-1">
                            <div className="flex flex-col">
                                <ImageIcon size={20} className="text-primary mb-1" fill="currentColor" />
                                <span className="text-xs font-black uppercase tracking-tighter text-muted">Total Photos</span>
                            </div>
                            <span className="text-6xl font-black text-primary leading-none">{stats?.total_photos ?? 0}</span>
                        </div>

                        {/* Top Right: Faces Detected */}
                        <div className="flex items-center justify-between p-4 flex-1 line-clamp-1">
                            <div className="flex flex-col">
                                <Scan size={20} className="text-primary mb-1" fill="currentColor" strokeWidth={2.5} />
                                <span className="text-xs font-black uppercase tracking-tighter text-muted">Faces Detected</span>
                            </div>
                            <span className="text-6xl font-black text-primary leading-none">{stats?.total_faces ?? 0}</span>
                        </div>

                        {/* Bottom Left: People Cluster */}
                        <div className="flex items-center justify-between p-4 flex-1">
                            <div className="flex flex-col">
                                <Users size={20} className="text-primary mb-1" fill="currentColor" />
                                <span className="text-xs font-black uppercase tracking-tighter text-muted">People Cluster</span>
                            </div>
                            <span className="text-6xl font-black text-primary leading-none">{stats?.total_persons ?? 0}</span>
                        </div>

                        {/* Bottom Right: Enrolled */}
                        <div className="flex items-center justify-between p-4 flex-1">
                            <div className="flex flex-col">
                                <UserCheck size={20} className="text-primary mb-1" fill="currentColor" />
                                <span className="text-xs font-black uppercase tracking-tighter text-muted">Enrolled</span>
                            </div>
                            <span className="text-6xl font-black text-primary leading-none">{stats?.total_enrolled ?? 0}</span>
                        </div>
                    </div>
                </div>

                {/* Donut Chart Card */}
                <div className="dash-card p-8 flex-1 flex flex-col sm:flex-row items-center gap-8 xl:gap-12">
                     <div className="relative w-48 h-48 xl:w-64 xl:h-64 flex items-center justify-center">
                         {/* Dynamic Donut Chart */}
                         <div className="absolute inset-0">
                             <ResponsiveContainer width="100%" height="100%">
                                 <PieChart>
                                     <Pie
                                         data={hasData ? chartData : [{ value: 1, color: theme === 'dark' ? "#1a1a1c" : "#f1f5f9" }]}
                                         innerRadius="75%"
                                         outerRadius="100%"
                                         paddingAngle={hasData ? 4 : 0}
                                         dataKey="value"
                                         stroke="none"
                                         startAngle={90}
                                         endAngle={-270}
                                     >
                                         {(hasData ? chartData : [{ color: theme === 'dark' ? "#1a1a1c" : "#f1f5f9" }]).map((entry, index) => (
                                             <Cell key={`cell-${index}`} fill={entry.color} />
                                         ))}
                                     </Pie>
                                 </PieChart>
                             </ResponsiveContainer>
                         </div>

                         {/* Center Text */}
                         <div className="text-center z-10">
                            <span className="text-2xl font-black text-primary">
                                {Math.round(((photosByStatus.completed ?? 0) / (stats?.total_photos || 1)) * 100)}%
                            </span>
                            <div className="text-[10px] font-bold text-muted uppercase">Success</div>
                         </div>
                    </div>

                    <div className="flex-1 grid grid-cols-2 gap-x-8 gap-y-4 w-full sm:w-auto">
                        <div className="flex items-center justify-between gap-3 border-b border-muted/10 pb-2">
                            <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-[#5EBF9E]" />
                                <span className="text-base font-bold text-secondary">Completed</span>
                            </div>
                            <span className="text-xl font-black text-primary">{photosByStatus.completed ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3 border-b border-muted/10 pb-2">
                            <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-[#4BA8FF]" />
                                <span className="text-base font-bold text-secondary">Processing</span>
                            </div>
                            <span className="text-xl font-black text-primary">{photosByStatus.processing ?? 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3 border-b border-muted/10 pb-2">
                            <div className="flex items-center gap-3">
                                <div className="w-3 h-3 rounded-full bg-[#FDE285]" />
                                <span className="text-base font-bold text-secondary">Pending</span>
                            </div>
                            <span className="text-xl font-black text-primary">{photosByStatus.pending ?? 0}</span>
                        </div>
                        <div className="flex flex-col gap-1 w-full border-b border-muted/10 pb-2">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-3 h-3 rounded-full bg-[#E87461]" />
                                    <span className="text-base font-bold text-secondary">Error</span>
                                </div>
                                <span className="text-xl font-black text-primary">{photosByStatus.error ?? 0}</span>
                            </div>
                            { (photosByStatus.error ?? 0) > 0 && (
                                <p className="text-[10px] text-rose-500 font-bold uppercase tracking-wider text-right animate-pulse">
                                    Use Self-Heal in System Health
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Right Column: Activity Log */}
            <div className="col-span-12 xl:col-span-5 h-full min-h-[500px]">
                <ActivityLog />
            </div>
        </div>
    );
}
