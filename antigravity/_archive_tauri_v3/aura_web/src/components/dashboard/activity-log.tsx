"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    ScrollText,
    AlertCircle,
    Info,
    CheckCircle2,
    AlertTriangle,
    Wifi,
    WifiOff,
    Loader2,
    Cpu,
    Cloud,
    Shield,
    Globe,
    Smartphone,
    Key,
    Activity,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface LogEntry {
    id: string;
    timestamp: string;   // HH:MM:SS
    level: "info" | "warn" | "warning" | "error" | "success" | "debug";
    message: string;
    logger?: string;
}

type ConnectionState = "connecting" | "live" | "disconnected" | "error";

// ── Level Config ───────────────────────────────────────────────────────────

const levelConfig: Record<string, { color: string; bg: string; border: string }> = {
    info:    { color: "#3B82F6", bg: "style-var", border: "border-blue-100 dark:border-blue-500/10" },
    debug:   { color: "#94A3B8", bg: "style-var", border: "border-slate-100 dark:border-slate-500/10" },
    warn:    { color: "#FBBF24", bg: "style-var", border: "border-amber-100 dark:border-amber-500/10" },
    warning: { color: "#FBBF24", bg: "style-var", border: "border-amber-100 dark:border-amber-500/10" },
    error:   { color: "#EF4444", bg: "style-var", border: "border-rose-100 dark:border-rose-500/10" },
    success: { color: "#22C55E", bg: "style-var", border: "border-emerald-100 dark:border-emerald-500/10" },
    critical:{ color: "#B91C1C", bg: "style-var", border: "border-red-200 dark:border-red-500/10" },
};

const loggerConfig: Record<string, { icon: React.ElementType; color: string }> = {
    'app.worker':   { icon: Cpu,        color: "#6366F1" }, // Indigo
    'app.cloud':    { icon: Cloud,      color: "#0EA5E9" }, // Sky
    'admin_router': { icon: Globe,      color: "#8B5CF6" }, // Violet
    'whatsapp':     { icon: Smartphone, color: "#22C55E" }, // Green
    'setup_auth':   { icon: Key,        color: "#F59E0B" }, // Amber
    'system':       { icon: Shield,     color: "#64748B" }, // Slate
    'raw':          { icon: ScrollText, color: "#94A3B8" },
};

const MAX_LOGS = 200;
let _idCounter = 0;

// ── WebSocket URL ──────────────────────────────────────────────────────────
import { WS_BASE } from "@/lib/api";
const WS_URL = `${WS_BASE}/logs`;

// ── Component ──────────────────────────────────────────────────────────────

export function ActivityLog() {
    const scrollRef      = useRef<HTMLDivElement>(null);
    const wsRef          = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const shouldReconnect = useRef(true);

    const [logs,       setLogs]       = useState<LogEntry[]>([]);
    const [connState,  setConnState]  = useState<ConnectionState>("connecting");
    const [autoScroll, setAutoScroll] = useState(true);

    // ── helpers ──────────────────────────────────────────────────────────

    const normaliseLevel = (raw: string): LogEntry["level"] => {
        const l = raw?.toLowerCase() ?? "info";
        if (l === "warning")  return "warn";
        if (l === "critical") return "error";
        if (!Object.prototype.hasOwnProperty.call(levelConfig, l)) return "info";
        return l as LogEntry["level"];
    };

    const formatNow = () => {
        const d = new Date();
        return [d.getHours(), d.getMinutes(), d.getSeconds()]
            .map((n) => String(n).padStart(2, "0"))
            .join(":");
    };

    const pushLog = useCallback((entry: Omit<LogEntry, "id">) => {
        setLogs((prev) => {
            const next = [...prev, { ...entry, id: `${Date.now()}-${_idCounter++}` }];
            return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
        });
    }, []);

    // ── WebSocket ─────────────────────────────────────────────────────────

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        setConnState("connecting");
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnState("live");
            pushLog({ timestamp: formatNow(), level: "info", message: "✓ Log stream connected to backend" });
        };

        ws.onmessage = (evt) => {
            try {
                const raw = JSON.parse(evt.data as string);
                // Backend sends: { timestamp, level, message, logger }
                // Timestamp from backend is a full datetime string — pull HH:MM:SS
                let ts = (raw.timestamp as string) ?? formatNow();
                const match = ts.match(/(\d{2}:\d{2}:\d{2})/);
                if (match) ts = match[1];

                pushLog({
                    timestamp: ts,
                    level:   normaliseLevel(raw.level ?? "info"),
                    message: raw.message ?? String(raw),
                    logger:  raw.logger,
                });
            } catch {
                pushLog({ timestamp: formatNow(), level: "warn", message: `Unparseable log: ${evt.data}` });
            }
        };

        ws.onclose = (e) => {
            if (!shouldReconnect.current) return;
            setConnState("disconnected");
            pushLog({ timestamp: formatNow(), level: "warn", message: `Log stream disconnected (code: ${e.code}) — reconnecting…` });
            reconnectTimer.current = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
            setConnState("error");
            // onclose will fire after onerror; let it handle reconnect
        };
    }, [pushLog]);

    useEffect(() => {
        shouldReconnect.current = true;
        connect();
        return () => {
            shouldReconnect.current = false;
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            wsRef.current?.close();
        };
    }, [connect]);

    // ── Auto-scroll ───────────────────────────────────────────────────────

    useEffect(() => {
        if (!autoScroll || !scrollRef.current) return;
        scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth",
        });
    }, [logs, autoScroll]);

    const handleScroll = () => {
        if (!scrollRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
        setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
    };

    // ── Connection badge ──────────────────────────────────────────────────

    const connBadge = {
        live:         { label: "Live",        icon: Wifi,     style: { background: "var(--accent-primary-dim)", color: "var(--accent-primary)", borderColor: "rgba(34,197,94,0.2)" } },
        connecting:   { label: "Connecting…", icon: Loader2,  style: { background: "var(--accent-amber-dim)",   color: "var(--accent-amber)",   borderColor: "rgba(245,158,11,0.2)" } },
        disconnected: { label: "Offline",     icon: WifiOff,  style: { background: "var(--bg-tertiary)",        color: "var(--text-muted)",     borderColor: "rgba(255,255,255,0.05)" } },
        error:        { label: "Error",       icon: WifiOff,  style: { background: "var(--accent-rose-dim)",    color: "var(--accent-rose)",    borderColor: "rgba(239,68,68,0.2)" } },
    }[connState] ?? { label: "Unknown", icon: WifiOff, style: {} };

    const BadgeIcon = connBadge.icon;

    return (
        <motion.div
            className="dash-card p-6 flex flex-col h-full"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.4 }}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-primary">Activity Log</h2>
                <div className="flex gap-2">
                    {/* Live Badge */}
                    <div 
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-wider transition-all ${
                            connState === 'live' 
                                ? 'bg-emerald-500/10 text-emerald-500 shadow-sm' 
                                : 'bg-elevated text-muted'
                        }`}
                    >
                        <BadgeIcon
                            size={10}
                            className={connState === "connecting" ? "animate-spin" : ""}
                        />
                        {connState === 'live' ? 'Live' : connBadge.label}
                    </div>

                    {/* Clear Button */}
                    <button
                        onClick={() => setLogs([])}
                        className="bg-[#E87461] text-white text-[10px] font-bold px-3 py-1 rounded opacity-80 hover:opacity-100 transition-opacity uppercase tracking-wider shadow-sm"
                    >
                        Clear
                    </button>
                </div>
            </div>

            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-premium scrollbar-hide transition-all duration-300"
                style={{ 
                    maskImage: !autoScroll && scrollRef.current && scrollRef.current.scrollTop > 5 ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none',
                    WebkitMaskImage: !autoScroll && scrollRef.current && scrollRef.current.scrollTop > 5 ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none'
                }}
            >
                {logs.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-muted gap-2 italic text-sm">
                        <Activity size={24} className="opacity-20 text-primary" />
                        No activity recorded yet
                    </div>
                )}

                <AnimatePresence initial={false}>
                    {logs.map((log) => {
                        const levelCfg = levelConfig[log.level] ?? levelConfig.info;
                        const loggerId = log.logger?.toLowerCase() || 'system';
                        let logInfo = loggerConfig[loggerId];
                        
                        // Fallback logic for loggers
                        if (!logInfo) {
                            if (loggerId.includes('worker')) logInfo = loggerConfig['app.worker'];
                            else if (loggerId.includes('cloud')) logInfo = loggerConfig['app.cloud'];
                            else if (loggerId.includes('whatsapp')) logInfo = loggerConfig['whatsapp'];
                            else logInfo = loggerConfig.system;
                        }

                        const LogIcon = logInfo.icon;
                        
                        return (
                            <motion.div
                                key={log.id}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className={`flex items-start gap-2 p-1.5 rounded-lg border ${levelCfg.border} transition-all group relative overflow-hidden`}
                                style={{ background: "var(--bg-log-item)" }}
                            >
                                <div className="mt-0.5 p-1.5 rounded-md bg-elevated shadow-sm border border-muted/5 flex-shrink-0">
                                    <LogIcon 
                                        size={11} 
                                        style={{ color: log.level === 'error' || log.level === 'warn' ? levelCfg.color : logInfo.color }}
                                        fill="currentColor"
                                        strokeWidth={1.5}
                                    />
                                </div>
                                
                                <div className="flex-1 flex flex-col gap-0 min-w-0">
                                    <div className="flex items-center justify-between mb-0">
                                        <span className="text-[8px] font-black uppercase tracking-widest opacity-70 group-hover:opacity-100 transition-opacity" style={{ color: logInfo.color }}>
                                            {log.logger || 'System'}
                                        </span>
                                        <span className="text-[8px] font-bold text-muted tabular-nums">
                                            {log.timestamp}
                                        </span>
                                    </div>
                                    <p 
                                        className="text-[12px] leading-tight break-words font-medium tracking-tight"
                                        style={{ 
                                            color: log.level === 'error' || log.level === 'warn' || log.level === 'success' 
                                                ? levelCfg.color 
                                                : 'var(--text-primary)'
                                        }}
                                    >
                                        {log.message}
                                    </p>
                                </div>
                            </motion.div>
                        );
                    })}
                </AnimatePresence>
            </div>

            {/* Scroll-to-bottom nudge when autoscroll is paused */}
            <AnimatePresence>
                {!autoScroll && logs.length > 0 && (
                    <motion.button
                        initial={{ opacity: 0, y: 10, x: "-50%" }}
                        animate={{ opacity: 1, y: 0, x: "-50%" }}
                        exit={{ opacity: 0, y: 10, x: "-50%" }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setAutoScroll(true)}
                        className="absolute bottom-6 left-1/2 z-20 text-[10px] px-4 py-1.5 rounded-full shadow-lg cursor-pointer font-bold bg-[#4BA8FF] text-white"
                    >
                        ↓ Scroll to latest
                    </motion.button>
                )}
            </AnimatePresence>
        </motion.div>
    );
}
