"use client";

import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
    MessageCircle,
    Users,
    Send,
    Smartphone,
    CheckCircle,
    AlertTriangle,
    Play,
    Square,
    Power
} from "lucide-react";
import { fetchWhatsAppStatus, startWhatsApp, stopWhatsApp } from "@/lib/api";
import { useSystemStore } from "@/lib/store";

export default function WhatsAppPage() {
    const queryClient = useQueryClient();
    const setPageTitle = useSystemStore((s) => s.setPageTitle);
    useEffect(() => { setPageTitle("WhatsApp"); }, [setPageTitle]);

    const { data: waStatus, isLoading } = useQuery({
        queryKey: ["admin-whatsapp"],
        queryFn: fetchWhatsAppStatus,
        refetchInterval: 5000,
        retry: false,
    });

    const startMutation = useMutation({
        mutationFn: startWhatsApp,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-whatsapp"] });
        }
    });

    const stopMutation = useMutation({
        mutationFn: stopWhatsApp,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-whatsapp"] });
        }
    });

    return (
        <div className="space-y-4 animate-fade-in" style={{ maxWidth: 800 }}>
            {/* Status cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <motion.div className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>

                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <Users size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <p className="text-xl font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>
                        {isLoading ? "—" : waStatus?.total_enrolled ?? 0}
                    </p>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Total Enrolled</p>
                </motion.div>

                <motion.div className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>

                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <Send size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <p className="text-xl font-bold" style={{ fontFamily: "var(--font-jakarta)" }}>
                        {isLoading ? "—" : waStatus?.sendable ?? 0}
                    </p>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Sendable (with phone)</p>
                </motion.div>

                <motion.div className="card-base p-4 relative overflow-hidden"
                    initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>

                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5"
                        style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}>
                        <Smartphone size={17} strokeWidth={1.5} fill="currentColor" />
                    </div>
                    <div className="flex items-center gap-1.5">
                        {waStatus?.session_exists ? (
                            <CheckCircle size={14} style={{ color: "var(--accent-primary)" }} fill="currentColor" strokeWidth={1.5} />
                        ) : (
                            <AlertTriangle size={14} style={{ color: "var(--accent-amber)" }} fill="currentColor" strokeWidth={1.5} />
                        )}
                        <p className="text-[13px] font-semibold" style={{ color: "var(--text-primary)" }}>
                            {isLoading ? "..." : waStatus?.session_exists ? "Session Active" : "No Session"}
                        </p>
                    </div>
                    <p className="text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>WhatsApp Session</p>
                </motion.div>
            </div>

            {/* Process Control */}
            <motion.div className="card-base p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`px-3 py-2 rounded-lg border flex items-center gap-2 transition-all duration-300 shrink-0 ${waStatus?.is_running ? 'bg-[rgba(16,185,129,0.1)] border-[rgba(16,185,129,0.2)] text-[#10b981]' : 'bg-[rgba(245,158,11,0.05)] border-transparent text-[var(--text-tertiary)]'}`}>
                            <div className={`w-2 h-2 rounded-full ${waStatus?.is_running ? 'bg-[#10b981] animate-pulse shadow-[0_0_8px_#10b981]' : 'bg-[var(--text-muted)]'}`} />
                            <span className="text-[10px] font-black uppercase tracking-[0.15em]">
                                {isLoading ? "..." : waStatus?.is_running ? "Live" : "Offline"}
                            </span>
                        </div>
                        <div>
                            <h3 className="text-[13px] font-bold" style={{ color: "var(--text-primary)" }}>WhatsApp Sender Process</h3>
                            <p className="text-[10px] mt-0.5" style={{ color: "var(--text-secondary)" }}>
                                {waStatus?.is_running ? "Distributing photos to guests in real-time" : "Process is currently stopped"}
                            </p>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => waStatus?.is_running ? stopMutation.mutate() : startMutation.mutate()}
                            disabled={isLoading || startMutation.isPending || stopMutation.isPending}
                            className={`h-11 px-7 rounded-full transition-all flex items-center gap-3 disabled:opacity-50 border-2 shadow-lg ${(!isLoading && !startMutation.isPending && !stopMutation.isPending) ? 'cursor-pointer hover:scale-[1.02] active:scale-[0.98]' : 'cursor-not-allowed'}`}
                            style={{ 
                                background: waStatus?.is_running ? "#f43f5e" : "#10b981", 
                                borderColor: "rgba(255, 255, 255, 0.2)",
                                color: "#ffffff" 
                            }}
                        >
                            {waStatus?.is_running ? (
                                <Square size={16} fill="currentColor" strokeWidth={0} />
                            ) : (
                                <Play size={16} fill="currentColor" strokeWidth={0} className="ml-0.5" />
                            )}
                            <span className="text-[12px] font-black uppercase tracking-[0.05em]">
                                {waStatus?.is_running ? "Stop Process" : "Start Process"}
                            </span>
                        </button>
                    </div>
                </div>
            </motion.div>

            {/* How It Works */}
            <motion.div className="card-base p-5" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
                <div className="flex items-center gap-2 mb-4">
                    <MessageCircle size={15} style={{ color: "var(--accent-primary)" }} fill="currentColor" />
                    <h3 className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>
                        How It Works
                    </h3>
                </div>
                <div className="space-y-2">
                    {[
                        { step: "1", color: "var(--accent-cyan)", text: "Guests enroll via the guest portal and provide their phone number." },
                        { step: "2", color: "var(--accent-violet)", text: "AURA matches their face to event photos and prepares download links." },
                        { step: "3", color: "var(--accent-primary)", text: "The WhatsApp sender automatically delivers photo links to each guest." },
                    ].map((item) => (
                        <div key={item.step} className="flex items-start gap-3 p-3 rounded-lg" style={{ background: "var(--bg-inner)" }}>
                            <span
                                className="w-5 h-5 rounded-md flex items-center justify-center shrink-0 text-[10px] font-bold"
                                style={{ background: item.color, color: "var(--bg-deep)" }}
                            >
                                {item.step}
                            </span>
                            <p className="text-[12px] leading-relaxed" style={{ color: "var(--text-secondary)" }}>{item.text}</p>
                        </div>
                    ))}
                </div>
            </motion.div>
        </div>
    );
}
