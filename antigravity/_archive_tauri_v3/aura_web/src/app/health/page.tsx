"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
    HeartPulse,
    RefreshCw,
    AlertTriangle,
    CheckCircle,
    Cpu,
    Database,
    Wifi,
    HardDrive,
    Loader2,
    Wrench,
    ImageOff,
} from "lucide-react";
import {
    fetchHealth,
    fetchGPUStatus,
    fetchStuckPhotos,
    runSelfHeal,
    fixStuckPhotos,
    type GPUInfo,
    type StuckPhoto,
} from "@/lib/api";
import { useSystemStore } from "@/lib/store";

export default function HealthPage() {
    const setPageTitle = useSystemStore((s) => s.setPageTitle);
    const queryClient = useQueryClient();
    const [isScrolled, setIsScrolled] = useState(false);

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setIsScrolled(e.currentTarget.scrollTop > 5);
    };

    useEffect(() => { setPageTitle("System Health"); }, [setPageTitle]);

    const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 5000 });
    const { data: gpu } = useQuery({ queryKey: ["admin-gpu"], queryFn: fetchGPUStatus, retry: false });
    const { data: stuck, isLoading: stuckLoading } = useQuery({ queryKey: ["admin-stuck"], queryFn: fetchStuckPhotos, retry: false });

    const selfHealMutation = useMutation({
        mutationFn: runSelfHeal,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-stuck"] });
            queryClient.invalidateQueries({ queryKey: ["stats"] });
        },
    });

    const resetStuckMutation = useMutation({
        mutationFn: () => fixStuckPhotos("reset"),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-stuck"] }),
    });

    const serverOnline = health?.status === "healthy";

    return (
        <div 
            onScroll={handleScroll}
            className="h-full overflow-y-auto px-10 -mx-10 space-y-4 animate-fade-in scrollbar-premium transition-all duration-300" 
            style={{ 
                maxWidth: 960 + 80, 
                maskImage: isScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none',
                WebkitMaskImage: isScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none'
            }}
        >
            {/* Service Status */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <StatusCard title="FastAPI Server" icon={Wifi} online={serverOnline}
                    detail={serverOnline ? "Responding on :8000" : "Not reachable"}
                    color="var(--accent-primary)" delay={0} />
                <StatusCard title="GPU Acceleration" icon={Cpu}
                    online={gpu?.cuda_provider_available ?? false}
                    detail={gpu?.gpu_found ? `${gpu.gpu_name} (${gpu.vram_mb} MB)` : "No GPU detected"}
                    color="var(--accent-amber)" delay={0.05} />
                <StatusCard title="Database" icon={Database} online={serverOnline}
                    detail={serverOnline ? "SQLite connected" : "Unavailable"}
                    color="var(--accent-violet)" delay={0.1} />
            </div>

            {/* GPU Details */}
            {gpu && (
                <motion.div className="card-base p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                    <div className="flex items-center gap-2 mb-4">
                        <HardDrive size={15} style={{ color: "var(--accent-amber)" }} />
                        <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>GPU Details</h3>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[12px]">
                        <InfoItem label="GPU" value={gpu.gpu_name} />
                        <InfoItem label="Architecture" value={gpu.gpu_architecture} />
                        <InfoItem label="Compute" value={`${gpu.compute_capability}`} />
                        <InfoItem label="VRAM" value={`${gpu.vram_mb} MB`} />
                        <InfoItem label="Driver" value={gpu.driver_version} />
                        <InfoItem label="CUDA" value={gpu.cuda_installed ? gpu.cuda_version : "Not installed"} ok={gpu.cuda_installed} />
                        <InfoItem label="cuDNN" value={gpu.cudnn_installed ? gpu.cudnn_version : "Not installed"} ok={gpu.cudnn_installed} />
                        <InfoItem label="ORT-GPU" value={gpu.ort_gpu_installed ? "Installed" : "Not installed"} ok={gpu.ort_gpu_installed} />
                    </div>
                    <p className="mt-3 text-[11px] px-3 py-2 rounded-md" style={{ background: "var(--bg-inner)", color: "var(--text-secondary)" }}>
                        {gpu.status_message}
                    </p>
                </motion.div>
            )}

            {/* Stuck Photos */}
            <motion.div className="card-base p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
                <div className="flex items-center gap-2 mb-3">
                    <ImageOff size={15} style={{ color: "var(--accent-rose)" }} />
                    <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>Stuck Photos</h3>
                    <span className={`badge ml-auto ${(stuck?.length ?? 0) > 0 ? "badge-danger" : "badge-success"}`}>
                        {stuck?.length ?? 0} stuck
                    </span>
                </div>

                {stuckLoading ? (
                    <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>Loading...</p>
                ) : (stuck?.length ?? 0) === 0 ? (
                    <p className="text-[12px] flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
                        <CheckCircle size={13} style={{ color: "var(--accent-primary)" }} /> No stuck photos
                    </p>
                ) : (
                    <div className="space-y-1.5">
                        {stuck?.slice(0, 10).map((p: StuckPhoto) => (
                            <div key={p.id} className="flex items-center gap-3 text-[11px] px-3 py-2 rounded-md" style={{ background: "var(--bg-inner)" }}>
                                <AlertTriangle size={11} style={{ color: "var(--accent-amber)" }} fill="currentColor" />
                                <span className="truncate flex-1" style={{ color: "var(--text-secondary)" }}>{p.path}</span>
                                <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: "10px" }}>ID:{p.id}</span>
                            </div>
                        ))}
                    </div>
                )}

                {(stuck?.length ?? 0) > 0 && (
                    <button
                        onClick={() => resetStuckMutation.mutate()}
                        disabled={resetStuckMutation.isPending}
                        className="btn-desktop btn-desktop-danger mt-3"
                    >
                        {resetStuckMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                        Reset All to Pending
                    </button>
                )}
            </motion.div>

            {/* Self-Heal */}
            <motion.div className="card-base p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
                <div className="flex items-center gap-2 mb-3">
                    <Wrench size={15} style={{ color: "var(--accent-cyan)" }} />
                    <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>Self-Healing</h3>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "var(--text-secondary)" }}>
                    Recover photos from <b>Error</b> or <b>Processing</b> states, repair orphaned face records, and recalculate person centroids.
                </p>
                <button
                    onClick={() => selfHealMutation.mutate()}
                    disabled={selfHealMutation.isPending}
                    className="btn-desktop btn-desktop-primary"
                >
                    {selfHealMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Wrench size={13} fill="currentColor" strokeWidth={1.5} />}
                    {selfHealMutation.isPending ? "Healing..." : "Run Self-Heal"}
                </button>

                {selfHealMutation.isSuccess && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="mt-3 p-2.5 rounded-md text-[11px]"
                        style={{ background: "var(--accent-primary-dim)", color: "var(--accent-primary)" }}
                    >
                        <CheckCircle size={12} className="inline mr-1" /> Self-healing completed successfully
                    </motion.div>
                )}
            </motion.div>
        </div>
    );
}

function StatusCard({ title, icon: Icon, online, detail, color, delay }: {
    title: string; icon: typeof Cpu; online: boolean; detail: string; color: string; delay: number;
}) {
    return (
        <motion.div
            className="card-base p-4 relative overflow-hidden"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay }}
        >
            
            <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ background: "var(--bg-elevated)", color }}>
                    <Icon size={17} strokeWidth={1.5} fill="currentColor" />
                </div>
                <div>
                    <p className="text-[13px] font-semibold" style={{ color: "var(--text-primary)" }}>{title}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                        <div className={`status-dot ${online ? "online" : "offline"}`} />
                        <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>{detail}</span>
                    </div>
                </div>
            </div>
        </motion.div>
    );
}

function InfoItem({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
    return (
        <div>
            <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</p>
            <p className="text-[12px] font-medium flex items-center gap-1 mt-0.5" style={{ color: "var(--text-primary)" }}>
                {ok !== undefined && (
                    ok ? <CheckCircle size={11} style={{ color: "var(--accent-primary)" }} fill="currentColor" strokeWidth={1.5} />
                        : <AlertTriangle size={11} style={{ color: "var(--accent-amber)" }} fill="currentColor" strokeWidth={1.5} />
                )}
                {value}
            </p>
        </div>
    );
}
