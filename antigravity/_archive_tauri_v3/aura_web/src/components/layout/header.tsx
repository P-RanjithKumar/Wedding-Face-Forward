import { useEffect, useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Sun, Moon, Zap, Play, Square, Loader2, Key, Palette } from "lucide-react";
import { fetchHealth, fetchAuthStatus, triggerReauth, fetchWorkerStatus, startWorker, stopWorker } from "@/lib/api";
import { useSystemStore } from "@/lib/store";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { CommandPalette } from "@/components/ui/command-palette";
import { ECGIndicator } from "@/components/ui/ecg-indicator";

const GRADIENTS: Record<string, Record<string, { top: string; mid: string; bottom: string }>> = {
    dark: {
        graphite: { top: "#232526", mid: "#323436", bottom: "#414345" }
    },
    light: {
        slate: { top: "#f1f5f9", mid: "#e2e8f0", bottom: "#e2e8f0" },
        arctic: { top: "#8399a2", mid: "#b9c9cf", bottom: "#eef2f3" },
        dusk: { top: "#727a9a", mid: "#a5abc2", bottom: "#d8dbe9" },
        forest_bloom: { top: "#a4c6b8", mid: "#81848b", bottom: "#5e435d" }
    }
};

const PAGE_CONTENT: Record<string, { title: string; desc: string }> = {
    "/": {
        title: "Welcome back!",
        desc: "Monitor photo processing, manage people, and control your event pipeline."
    },
    "/people": {
        title: "People Directory",
        desc: "Manage faces, identities, and grouped contacts for your event."
    },
    "/processing": {
        title: "AI Processing",
        desc: "Watch AURA detect and process faces in real-time."
    },
    "/cloud": {
        title: "Cloud Sync",
        desc: "Manage your remote storage, backups, and data synchronization."
    },
    "/whatsapp": {
        title: "WhatsApp Center",
        desc: "Control message delivery and outbound notification status."
    },
    "/health": {
        title: "System Health",
        desc: "Monitor server performance, logs, and database integrity."
    },
    "/settings": {
        title: "Settings",
        desc: "Configure core engine parameters and application behavior."
    }
};

export function Header() {
    const { serverOnline, setServerOnline, theme, setTheme, gradientMood, setGradientMood } = useSystemStore();
    const [isRunning, setIsRunning] = useState(false);
    const [showPalette, setShowPalette] = useState(false);
    const paletteRef = useRef<HTMLDivElement>(null);
    const pathname = usePathname();

    const queryClient = useQueryClient();

    const content = PAGE_CONTENT[pathname] || PAGE_CONTENT["/"];

    const { data: health, isLoading: healthLoading } = useQuery({
        queryKey: ["health"],
        queryFn: fetchHealth,
        refetchInterval: 5_000,
        retry: 2,
    });

    const { data: auth, isLoading: authLoading } = useQuery({
        queryKey: ["auth-status"],
        queryFn: fetchAuthStatus,
        refetchInterval: 10_000,
    });

    const reauthMutation = useMutation({
        mutationFn: triggerReauth,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["auth-status"] });
        },
        onError: (error) => {
            console.error("Reauth failed:", error);
            alert("Authentication failed. Please check the backend logs for details.");
        }
    });

    // Check Worker Status
    const { data: workerStatus, isLoading: workerStatusLoading } = useQuery({
        queryKey: ["worker-status"],
        queryFn: fetchWorkerStatus,
        refetchInterval: 3000,
    });

    useEffect(() => {
        if (workerStatus) {
            setIsRunning(workerStatus.is_running);
        }
    }, [workerStatus]);

    // Mutation to Start/Stop Worker
    const toggleWorkerMutation = useMutation({
        mutationFn: async (currentState: boolean) => {
            if (currentState) {
                return await stopWorker();
            } else {
                return await startWorker();
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["worker-status"] });
        },
        onError: (error, variables) => {
            console.error("Failed to toggle worker:", error);
            alert("Action failed. Please check the logs.");
            setIsRunning(variables); // Revert UI
        }
    });

    const handleToggleWorker = () => {
        const previousState = isRunning;
        setIsRunning(!previousState); // Optimistic UI update
        toggleWorkerMutation.mutate(previousState);
    };

    // Apply Gradient Variables to Body
    useEffect(() => {
        const root = document.documentElement;
        const palette = GRADIENTS[theme][gradientMood] || GRADIENTS[theme].slate;

        root.style.setProperty("--dash-bg-top", palette.top);
        root.style.setProperty("--dash-bg-mid", palette.mid);
        root.style.setProperty("--dash-bg-bottom", palette.bottom);
    }, [gradientMood, theme]);

    // Close palette on click outside
    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (paletteRef.current && !paletteRef.current.contains(e.target as Node)) {
                setShowPalette(false);
            }
        };
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    useEffect(() => {
        setServerOnline(health?.status === "healthy");
    }, [health, setServerOnline]);

    return (
        <header className="w-full pt-8 px-8 pl-[112px] pb-4 flex items-start justify-between select-none relative z-50">
            {/* Left: Greeting */}
            <div className="flex gap-6 min-h-[100px]">
                <div className="flex flex-col gap-1">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={pathname}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -5 }}
                            transition={{ duration: 0.2 }}
                        >
                            <h1 className="text-2xl font-bold text-primary">{content.title}</h1>
                            <p className="text-sm text-secondary font-medium">
                                {content.desc}
                            </p>
                        </motion.div>
                    </AnimatePresence>

                    <CommandPalette />
                </div>
            </div>

            {/* Right: Action Buttons */}
            <div className="flex items-center gap-3">
                {/* Palette EXPERIMENT Button */}
                <div className="relative" ref={paletteRef}>
                    <button
                        onClick={() => setShowPalette(!showPalette)}
                        className={`icon-circle ${showPalette ? 'ring-2 ring-primary bg-primary/10' : ''}`}
                        title="Experiment with Gradients"
                    >
                        <Palette size={20} className={showPalette ? "text-primary" : "text-secondary"} strokeWidth={1.5} />
                    </button>

                    <AnimatePresence>
                        {showPalette && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                                className="absolute right-0 mt-3 p-4 dash-card min-w-[200px] grid grid-cols-2 gap-3 shadow-2xl z-[100] backdrop-blur-xl border border-white/10"
                            >
                                {Object.keys(GRADIENTS[theme]).map((mood) => {
                                    const colors = GRADIENTS[theme][mood];
                                    return (
                                        <button
                                            key={mood}
                                            onClick={() => {
                                                setGradientMood(mood);
                                                setShowPalette(false);
                                            }}
                                            className={`p-2 rounded-xl border-2 transition-all flex flex-col items-center gap-1 hover:scale-105 active:scale-95 ${gradientMood === mood ? 'border-primary bg-primary/5' : 'border-transparent bg-elevated hover:bg-white/5'
                                                }`}
                                        >
                                            <div
                                                className="w-8 h-8 rounded-full shadow-inner border border-white/10"
                                                style={{ background: `linear-gradient(135deg, ${colors.top}, ${colors.bottom})` }}
                                            />
                                            <span className="text-[10px] font-bold uppercase tracking-tight text-primary">{mood}</span>
                                        </button>
                                    );
                                })}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                <button
                    onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                    className="icon-circle"
                    title={theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}
                >
                    {theme === "light" ? <Moon size={20} className="text-primary" fill="currentColor" strokeWidth={1.5} /> : <Sun size={20} className="text-primary" fill="currentColor" strokeWidth={1.5} />}
                </button>

                <button
                    onClick={() => reauthMutation.mutate()}
                    disabled={reauthMutation.isPending || authLoading}
                    className={`icon-circle border-none outline-none group relative ${reauthMutation.isError ? 'bg-rose-500/20' :
                            !auth?.token_exists ? 'bg-rose-500/10' :
                                auth?.token_valid ? 'bg-emerald-500/10' : 'bg-amber-500/10'
                        }`}
                >
                    {reauthMutation.isPending || authLoading ? (
                        <Loader2 size={20} className="text-muted animate-spin" />
                    ) : (
                        <Key
                            size={20}
                            className={!auth?.token_exists ? 'text-rose-500' : auth?.token_valid ? 'text-emerald-500' : 'text-amber-500'}
                            fill="currentColor"
                        />
                    )}
                </button>

                <div className="flex items-center justify-center overflow-visible" title={isRunning ? "AI Worker Active" : "AI Worker Idle"}>
                    <ECGIndicator active={isRunning} />
                </div>


                <button
                    onClick={handleToggleWorker}
                    disabled={toggleWorkerMutation.isPending || workerStatusLoading}
                    className={`cursor-pointer flex items-center gap-2 px-4 py-2 rounded-full shadow-lg hover:scale-105 transition-all font-bold text-white border-none outline-none disabled:opacity-50 disabled:cursor-not-allowed ${
                        isRunning ? 'bg-rose-500 hover:bg-rose-600 shadow-rose-500/20' : 'bg-emerald-500 hover:bg-emerald-600 shadow-emerald-500/20'
                    }`}
                >


                    <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
                        {workerStatusLoading || toggleWorkerMutation.isPending ? (
                            <Loader2 size={16} className="text-white animate-spin" />
                        ) : isRunning ? (
                            <Square size={14} className="text-white fill-current" />
                        ) : (
                            <Play size={16} className="text-white fill-current ml-1" />
                        )}
                    </div>
                    {isRunning ? "STOP" : "START"}
                </button>
            </div>
        </header>
    );
}
