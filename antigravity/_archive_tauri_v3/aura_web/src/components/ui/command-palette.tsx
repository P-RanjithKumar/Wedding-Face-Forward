"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { Search, Users, Image as ImageIcon, Settings, Activity, Command, ArrowRight, Cloud, MessageCircle, HeartPulse, Cpu, Database, RefreshCw, FolderOpen, Wrench, BarChart3, Zap, UsersRound, HardDrive, Smartphone, Sun, Moon, Play, Square, ShieldCheck, ZapOff } from "lucide-react";
import { useSystemStore } from "@/lib/store";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
    fetchWhatsAppStatus, startWhatsApp, stopWhatsApp,
    fetchWorkerStatus, startWorker, stopWorker,
    fetchSettings, updateSettings,
    runSelfHeal
} from "@/lib/api";

type SearchItem = {
    id: string;
    type: "page" | "person" | "action";
    title: string;
    subtitle?: string;
    keywords?: string[];
    icon: React.ReactNode;
    href?: string;
    action?: () => void;
};

export function CommandPalette() {
    const [query, setQuery] = useState("");
    const [isFocused, setIsFocused] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);

    const inputRef = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const router = useRouter();
    const queryClient = useQueryClient();

    const { theme, setTheme } = useSystemStore();

    // --- LIVE QUERIES ---
    const { data: whatsappStatus } = useQuery({
        queryKey: ["admin-whatsapp-status"],
        queryFn: fetchWhatsAppStatus,
        enabled: isFocused // Only fetch when palette is active
    });

    const { data: workerStatus } = useQuery({
        queryKey: ["admin-worker-status"],
        queryFn: fetchWorkerStatus,
        enabled: isFocused
    });

    const { data: settings } = useQuery({
        queryKey: ["admin-settings"],
        queryFn: fetchSettings,
        enabled: isFocused
    });

    // --- MUTATIONS ---
    const waStartMutation = useMutation({
        mutationFn: startWhatsApp,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-whatsapp-status"] })
    });
    const waStopMutation = useMutation({
        mutationFn: stopWhatsApp,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-whatsapp-status"] })
    });

    const workerStartMutation = useMutation({
        mutationFn: startWorker,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-worker-status"] })
    });
    const workerStopMutation = useMutation({
        mutationFn: stopWorker,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-worker-status"] })
    });

    const settingsMutation = useMutation({
        mutationFn: updateSettings,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-settings"] })
    });

    // Helper to toggle a boolean setting
    const toggleSetting = (key: string) => {
        const currentValue = settings?.[key] === "true";
        settingsMutation.mutate({ [key]: currentValue ? "false" : "true" });
    };

    // Data for the search palette
    const searchItems: SearchItem[] = [
        // --- MAIN NAVIGATION ---
        { id: "p0", type: "page", title: "Dashboard", subtitle: "System overview and activity", keywords: ["home", "statistics", "main", "overview", "summary", "dashboard", "usage", "charts"], icon: <BarChart3 size={16} />, href: "/" },
        { id: "p1", type: "page", title: "People Directory", subtitle: "Manage guests, faces, and clusters", keywords: ["gallery", "roster", "members", "profiles", "contacts", "attendance", "directory", "listing", "people", "names", "clients", "faces", "guests", "clusters", "recognition", "faces", "guests", "enrollment"], icon: <Users size={16} />, href: "/people" },
        { id: "p2", type: "page", title: "AI Processing", subtitle: "Live background task status", keywords: ["ai", "live", "status", "queue", "processing", "tasks", "monitor", "activity", "loading", "compute", "engine", "realtime", "performance", "logs", "work", "running", "engine", "inference", "stats", "breakdown"], icon: <Zap size={16} />, href: "/processing" },
        { id: "p3", type: "page", title: "System Settings", subtitle: "Configure AURA engine behavior", keywords: ["config", "engine", "preferences", "setup", "options", "parameter", "control", "admin", "management", "tools", "advanced", "profile", "customization", "global", "defaults", "variables", "edit configuration"], icon: <Settings size={16} />, href: "/settings" },
        { id: "p4", type: "page", title: "Cloud Sync", subtitle: "Google Drive upload status", keywords: ["google drive", "upload", "sync", "backup", "cloud", "storage", "remote", "drive", "internet", "backup", "photos", "delivery", "progress", "donut chart"], icon: <Cloud size={16} />, href: "/cloud" },
        { id: "p5", type: "page", title: "WhatsApp Sender", subtitle: "Manage guest photo delivery", keywords: ["whatsapp", "messages", "sender", "delivery", "phone", "notification", "mobile", "chats", "bot", "auto", "broadcast", "enrolled", "session", "automation"], icon: <MessageCircle size={16} />, href: "/whatsapp" },
        { id: "p6", type: "page", title: "System Health", subtitle: "Monitor server & GPU status", keywords: ["server", "gpu", "health", "diagnotics", "repair", "maintenance", "logs", "errors", "uptime", "performance", "hardware", "cpu", "cuda", "nvidia", "stuck photos", "troubleshoot", "self-heal", "status"], icon: <HeartPulse size={16} />, href: "/health" },

        // --- CONTEXT-AWARE ACTIONS (Services) ---
        // WhatsApp Control
        { 
            id: "a-wa", 
            type: "action", 
            title: whatsappStatus?.is_running ? "Stop WhatsApp Sender" : "Start WhatsApp Sender", 
            subtitle: whatsappStatus?.is_running ? "Halt background message delivery" : "Resume background photo delivery", 
            keywords: ["whatsapp", "service", "start", "stop", "worker", "messages", "running", "delivery", "engine", "whatsapp bot", "wa sender", "message status"],
            icon: whatsappStatus?.is_running ? <Square size={16} className="text-rose-500" /> : <Play size={16} className="text-emerald-500" />, 
            action: () => whatsappStatus?.is_running ? waStopMutation.mutate() : waStartMutation.mutate()
        },
        // AI Worker Control
        { 
            id: "a-ai", 
            type: "action", 
            title: workerStatus?.is_running ? "Stop AI Engine" : "Start AI Engine", 
            subtitle: workerStatus?.is_running ? "Pause all face recognition tasks" : "Resume background processing", 
            keywords: ["ai", "engine", "start", "stop", "worker", "processing", "inference", "running", "tasks", "compute engine", "recognition status", "background processing"],
            icon: workerStatus?.is_running ? <ZapOff size={16} className="text-amber-500" /> : <Zap size={16} className="text-emerald-500" />, 
            action: () => workerStatus?.is_running ? workerStopMutation.mutate() : workerStartMutation.mutate()
        },

        // --- DYNAMIC SETTING TOGGLES ---
        { 
            id: "s-cloud", 
            type: "action", 
            title: settings?.["UPLOAD_QUEUE_ENABLED"] === "true" ? "Disable Cloud Sync" : "Enable Cloud Sync", 
            subtitle: "Global toggle for Google Drive uploads", 
            keywords: ["cloud", "sync", "upload", "drive", "internet", "toggle", "enable", "disable", "google drive sync", "cloud backup", "upload on off"],
            icon: <Cloud size={16} />, 
            action: () => toggleSetting("UPLOAD_QUEUE_ENABLED")
        },
        { 
            id: "s-gpu", 
            type: "action", 
            title: settings?.["GPU_ACCELERATION"] === "true" ? "Disable GPU Acceleration" : "Enable GPU Acceleration", 
            subtitle: "Toggle NVIDIA CUDA processing", 
            keywords: ["gpu", "cuda", "acceleration", "hardware", "nvidia", "toggle", "enable", "disable", "speed", "graphics card", "render speed", "video acceleration"],
            icon: <Cpu size={16} />, 
            action: () => toggleSetting("GPU_ACCELERATION")
        },

        // --- DEEP SETTINGS (Direct Access) ---
        { id: "s1", type: "action", title: "Event Root Folder", subtitle: "Change photo source directory", keywords: ["path", "folder", "root", "directory", "images", "source", "location", "storage", "files", "event", "home folder", "watch directory", "input folder"], icon: <FolderOpen size={16} />, href: "/settings" },
        { id: "s2", type: "action", title: "Database Path", subtitle: "SQLite database file location", keywords: ["db", "sqlite", "database", "storage", "sql", "meta", "file", "location", "path", "metadata", "save", "data store"], icon: <Database size={16} />, href: "/settings" },
        { id: "s3", type: "action", title: "Worker Threads", subtitle: "Adjust number of parallel tasks", keywords: ["workers", "threads", "multi-threading", "speed", "performance", "cpu usage", "background workers", "concurrent", "parallelism", "number of workers", "processing power", "cores", "compute power"], icon: <Cpu size={16} />, href: "/settings" },
        { id: "s4", type: "action", title: "Cluster Threshold", subtitle: "Face matching sensitivity (0.0-1.0)", keywords: ["facial", "matching", "sensitivity", "accuracy", "strict", "lenient", "matching", "recognition", "threshold", "distance", "face match", "cluster logic", "similarity"], icon: <UsersRound size={16} />, href: "/settings" },
        { id: "s5", type: "action", title: "Scan Interval", subtitle: "Frequency of folder scanning", keywords: ["scan", "interval", "timer", "watch", "folder", "filesystem", "refresh", "period", "delay", "seconds", "frequency", "poll", "check rate"], icon: <RefreshCw size={16} />, href: "/settings" },
        { id: "s6", type: "action", title: "Log Level", subtitle: "Verbosity (DEBUG, INFO, etc)", keywords: ["logs", "verbose", "debug", "warning", "info", "errors", "terminal", "output", "verbosity", "tracing", "syslog", "console level"], icon: <Activity size={16} />, href: "/settings" },

        // --- HARDWARE & HEALTH ---
        { id: "h1", type: "action", title: "GPU Details", subtitle: "Specs, CUDA, & Driver versions", keywords: ["vram", "architecture", "driver", "cudnn", "ort-gpu", "hardware info", "video memory", "specs", "nvidia info"], icon: <HardDrive size={16} />, href: "/health" },
        { id: "h2", type: "action", title: "Self-Healing Repair", subtitle: "Recover stuck photos & fix DB", keywords: ["fix", "repair", "heal", "stuck", "error", "database", "maintenance", "cleaning", "recovery", "troubleshoot", "wrench", "stale", "centroids", "orphans", "self heal", "auto repair"], icon: <Wrench size={16} />, action: () => { 
            runSelfHeal().then(() => {
                queryClient.invalidateQueries();
                router.push('/health');
            });
        } },
        { id: "h3", type: "action", title: "Stuck Photo Reset", subtitle: "Force reset all errors to Pending", keywords: ["reset", "errors", "stuck", "force", "retry", "pending", "restart photo", "broken process", "clear errors"], icon: <RefreshCw size={16} />, href: "/health" },

        // --- DYNAMIC THEME ACTION ---
        { 
            id: "a1", 
            type: "action", 
            title: theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode", 
            subtitle: theme === "light" ? "Switch to high-contrast dark theme" : "Switch to clean light interface", 
            keywords: theme === "light" 
                ? ["theme", "dark mode", "night mode", "display", "appearance", "dark", "color", "style", "skin", "ui", "interface", "vision", "brightness", "inversion", "contrast", "darkening"]
                : ["theme", "light mode", "day mode", "display", "appearance", "light", "color", "style", "skin", "ui", "interface", "vision", "brightness", "contrast", "bright", "whitening"],
            icon: theme === "light" ? <Moon size={16} /> : <Sun size={16} />, 
            action: () => setTheme(theme === "light" ? "dark" : "light")
        },
        
        { id: "a2", type: "action", title: "WhatsApp Session", subtitle: "Check/Link WhatsApp mobile", keywords: ["link device", "qr code", "whatsapp web", "session", "active", "status", "mobile link", "authenticate", "whatsapp link"], icon: <Smartphone size={16} />, href: "/whatsapp" },
    ];

    const filteredItems = query.trim() === "" ? [] : searchItems.filter((item) => {
        const lowerQuery = query.toLowerCase();
        return (
            item.title.toLowerCase().includes(lowerQuery) ||
            (item.subtitle && item.subtitle.toLowerCase().includes(lowerQuery)) ||
            (item.keywords && item.keywords.some(keyword => keyword.toLowerCase().includes(lowerQuery)))
        );
    });

    // Global shortcut to focus the input
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                inputRef.current?.focus();
            }
            if (e.key === "Escape" && isFocused) {
                e.preventDefault();
                inputRef.current?.blur();
                setQuery("");
                setIsFocused(false);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isFocused]);

    // Keyboard navigation within the dropdown
    useEffect(() => {
        const handleNavigation = (e: KeyboardEvent) => {
            if (!isFocused || filteredItems.length === 0) return;

            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex(prev => (prev + 1) % filteredItems.length);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex(prev => (prev - 1 + filteredItems.length) % filteredItems.length);
            } else if (e.key === "Enter") {
                e.preventDefault();
                const selected = filteredItems[selectedIndex];
                if (selected) {
                    if (selected.href) {
                        router.push(selected.href);
                    } else if (selected.action) {
                        selected.action();
                    }
                    setQuery("");
                    inputRef.current?.blur();
                    setIsFocused(false);
                }
            }
        };

        window.addEventListener("keydown", handleNavigation);
        return () => window.removeEventListener("keydown", handleNavigation);
    }, [isFocused, selectedIndex, filteredItems, router]);

    // Reset selection when typing
    useEffect(() => {
        setSelectedIndex(0);
    }, [query]);

    // Click outside handler to dismiss dropdown and blur
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setIsFocused(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const showDropdown = isFocused && query.trim().length > 0;
    const showOutline = isFocused || isHovered;

    return (
        <div ref={containerRef} className="mt-4 relative group z-50 w-[300px] h-10">
            {/* Background Overlay (pure frosted blur without dark overlay) */}
            <AnimatePresence>
                {isFocused && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="fixed inset-0 w-screen h-screen backdrop-blur-md bg-white/5 -z-10"
                        style={{ margin: 0, top: 0, left: 0 }}
                    />
                )}
            </AnimatePresence>

            {/* Unified Expanding Container */}
            <motion.div
                layout
                className={`absolute top-0 left-0 flex flex-col overflow-hidden transition-all duration-300 ${isFocused ? 'bg-[var(--bg-card)] border border-[var(--divider)] shadow-[var(--card-shadow)]' : 'bg-transparent'}`}
                style={{ 
                    borderRadius: showDropdown ? 24 : 18,
                    width: 300 
                }}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
            >
                {/* 1. The Search Bar Area */}
                <motion.div layout="position" className="relative w-full h-10 flex items-center shrink-0">
                    {!isFocused && (
                        <svg
                            className="absolute inset-x-0 bottom-0 pointer-events-none overflow-visible"
                            width="100%"
                            height="40"
                            viewBox="0 0 300 40"
                            fill="none"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <path
                                d="M 20 39.25 L 280 39.25"
                                stroke="currentColor"
                                strokeOpacity={showOutline && !isFocused ? 0 : 1}
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className={`transition-opacity duration-300 ${!showOutline ? 'text-muted' : 'text-primary'}`}
                            />
                            
                            {/* Left Growing Path (Starts from center-bottom, goes left, arc up, center-top) */}
                            <motion.path
                                d="M 150 39.25 L 20 39.25 A 19.25 19.25 0 0 1 20 0.75 L 150 0.75"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="text-primary"
                                initial={{ pathLength: 0.4148 }}
                                animate={{ pathLength: (showOutline && !isFocused) ? 1 : 0.4148, opacity: (showOutline && !isFocused) ? 1 : 0 }}
                                transition={{ duration: 0.4, ease: "easeInOut" }}
                            />

                            {/* Right Growing Path */}
                            <motion.path
                                d="M 150 39.25 L 280 39.25 A 19.25 19.25 0 0 0 280 0.75 L 150 0.75"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="text-primary"
                                initial={{ pathLength: 0.4148 }}
                                animate={{ pathLength: (showOutline && !isFocused) ? 1 : 0.4148, opacity: (showOutline && !isFocused) ? 1 : 0 }}
                                transition={{ duration: 0.4, ease: "easeInOut" }}
                            />
                        </svg>
                    )}

                    <Search size={16} className={`absolute left-4 transition-colors duration-300 z-10 ${showOutline || isFocused ? 'text-primary' : 'text-muted pointer-events-none'}`} />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onFocus={() => setIsFocused(true)}
                        placeholder="Search people, alerts, tools..."
                        className="w-full h-full bg-transparent outline-none pl-11 pr-12 text-sm z-10 text-[var(--text-primary)] placeholder:text-[var(--text-muted)] rounded-full"
                    />
                    {!isFocused && !query && (
                        <kbd className={`absolute right-2 hidden sm:flex items-center justify-center border border-[var(--divider)] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded text-[10px] font-mono font-bold pointer-events-none z-10 transition-colors duration-300 ${showOutline ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
                            ⌘K
                        </kbd>
                    )}
                </motion.div>

                {/* 2. The Dropdown Results within the expanding box */}
                <AnimatePresence>
                    {showDropdown && (
                        <motion.div
                            layout="position"
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2, ease: "easeInOut" }}
                            className="flex flex-col w-full"
                        >
                            {/* A divider between the search box and results */}
                            <div className="w-full h-px bg-[var(--divider)]" />
                            
                            <div className="max-h-[300px] overflow-y-auto py-2 shrink-0 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-[var(--text-muted)] hover:[&::-webkit-scrollbar-thumb]:bg-[var(--text-secondary)] [&::-webkit-scrollbar-thumb]:rounded-full">
                                {filteredItems.length === 0 ? (
                                    <div className="py-8 px-4 text-center text-[var(--text-secondary)]">
                                        <p className="text-sm">No results found for "{query}"</p>
                                    </div>
                                ) : (
                                    <ul className="px-2 shrink-0">
                                        {filteredItems.map((item, idx) => {
                                            const isSelected = idx === selectedIndex;
                                            return (
                                                <li key={item.id}>
                                                    <div
                                                        onMouseEnter={() => setSelectedIndex(idx)}
                                                        onClick={() => {
                                                            if (item.href) {
                                                                router.push(item.href);
                                                            } else if (item.action) {
                                                                item.action();
                                                            }
                                                            setQuery("");
                                                            setIsFocused(false);
                                                        }}
                                                        className={`flex items-center gap-3 px-3 py-2 cursor-pointer rounded-lg transition-all duration-200 ${isSelected
                                                                ? "bg-[var(--bg-elevated)]"
                                                                : "hover:bg-[var(--bg-elevated)]"
                                                            }`}
                                                    >
                                                        <div className={`p-1.5 rounded-md transition-colors duration-200 ${isSelected ? "bg-[var(--text-primary)] text-[var(--bg-card)] shadow-[var(--icon-shadow)]" : "bg-[var(--icon-bg)] text-[var(--text-muted)] border border-[var(--divider)]"}`}>
                                                            {item.icon}
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm font-semibold truncate leading-tight text-[var(--text-primary)]">{item.title}</p>
                                                            {item.subtitle && (
                                                                <p className={`text-[11px] truncate mt-0.5 ${isSelected ? "text-[var(--text-secondary)]" : "text-[var(--text-muted)]"}`}>
                                                                    {item.subtitle}
                                                                </p>
                                                            )}
                                                        </div>
                                                        {isSelected && (
                                                            <ArrowRight size={14} className="text-[var(--text-primary)] animate-pulse" />
                                                        )}
                                                    </div>
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </div>

                            <div className="flex items-center gap-3 px-3 py-2 border-t border-[var(--divider)] bg-[var(--bg-elevated)] text-[10px] text-[var(--text-muted)] font-medium shrink-0">
                                <span className="flex items-center gap-1">
                                    <span className="bg-[var(--icon-bg)] border border-[var(--divider)] rounded px-1.5 py-0.5 shadow-[var(--icon-shadow)] text-[var(--text-primary)]">↑↓</span> navigate
                                </span>
                                <span className="flex items-center gap-1">
                                    <span className="bg-[var(--icon-bg)] border border-[var(--divider)] rounded px-1.5 py-0.5 shadow-[var(--icon-shadow)] text-[var(--text-primary)]">↵</span> select
                                </span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}
