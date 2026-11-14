"use client";

import { useEffect, useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
    Settings,
    Save,
    FolderOpen,
    Database,
    Cpu,
    Cloud,
    Check,
    Loader2,
    RefreshCw,
    CheckCircle,
    Info,
    Activity,
    ShieldCheck,
    CpuIcon,
} from "lucide-react";
import { fetchSettings, updateSettings, fetchHealth, fetchGPUStatus } from "@/lib/api";
import { useSystemStore } from "@/lib/store";

interface SettingField {
    key: string;
    label: string;
    type: "text" | "number" | "boolean" | "select";
    group: string;
    description: string;
    longDescription?: string;
    options?: string[];
}

const SETTING_FIELDS: SettingField[] = [
    {
        key: "EVENT_ROOT", label: "Event Root Folder", type: "text", group: "Paths",
        description: "Root directory for event photos",
        longDescription: "AURA will watch this folder recursively for new photos. Ensure the path is absolute and accessible by the service account."
    },
    {
        key: "DB_PATH", label: "Database Path", type: "text", group: "Paths",
        description: "SQLite database file path",
        longDescription: "Where all metadata, face embeddings, and logs are stored. We recommend using an SSD for better IO performance."
    },
    {
        key: "WORKER_COUNT", label: "Worker Threads", type: "number", group: "Processing",
        description: "Number of parallel processing workers",
        longDescription: "Typically set to CPU core count / 2. Higher count increases speed but uses more RAM."
    },
    {
        key: "CLUSTER_THRESHOLD", label: "Cluster Threshold", type: "number", group: "Processing",
        description: "Face matching sensitivity (0.0-1.0)",
        longDescription: "Lower values (0.4) are strict for high accuracy; higher values (0.6) are more lenient for grouped faces."
    },
    {
        key: "SCAN_INTERVAL", label: "Scan Interval (sec)", type: "number", group: "Processing",
        description: "How often to scan for new photos",
        longDescription: "Setting this too low (e.g. 5s) might increase CPU overhead if the file system is large."
    },
    {
        key: "LOG_LEVEL", label: "Log Level", type: "select", group: "Processing",
        description: "Logging verbosity", options: ["DEBUG", "INFO", "WARNING", "ERROR"],
        longDescription: "Use DEBUG only for troubleshooting. INFO is recommended for normal production use."
    },
    {
        key: "DRIVE_ROOT_FOLDER_ID", label: "Drive Folder ID", type: "text", group: "Cloud",
        description: "Google Drive root folder ID",
        longDescription: "The unique ID from your Google Drive URL. AURA will sync processed photos here if enabled."
    },
    {
        key: "UPLOAD_QUEUE_ENABLED", label: "Upload Queue", type: "boolean", group: "Cloud",
        description: "Enable cloud upload queue",
        longDescription: "When enabled, AURA keeps a local queue of photos to be synced, ensuring no data loss during internet outages."
    },
    {
        key: "UPLOAD_WORKERS", label: "Upload Workers", type: "number", group: "Cloud",
        description: "Parallel upload threads",
        longDescription: "How many photos to upload at once. Recommended: 2-4 for average home connections."
    },
    {
        key: "UPLOAD_BATCH_SIZE", label: "Upload Batch Size", type: "number", group: "Cloud",
        description: "Photos per upload batch",
        longDescription: "Internal batching size for API requests. Higher values reduce overhead but increase RAM usage."
    },
    {
        key: "FOLDER_SYNC_INTERVAL", label: "Sync Interval (sec)", type: "number", group: "Cloud",
        description: "Folder sync check interval",
        longDescription: "How often AURA checks if the cloud folder structure matches the local state."
    },
    {
        key: "GPU_ACCELERATION", label: "GPU Acceleration", type: "boolean", group: "GPU",
        description: "Use NVIDIA GPU for face detection",
        longDescription: "Requires CUDA toolkit and compatible NVIDIA hardware. Increases detection speed by ~5-10x."
    },
    {
        key: "GPU_DEVICE_ID", label: "GPU Device ID", type: "number", group: "GPU",
        description: "Which GPU to use (0 = first)",
        longDescription: "If multiple GPUs are found, specify which one AURA should utilize for inference."
    },
];

const GROUP_ICONS: Record<string, typeof Settings> = {
    Paths: FolderOpen,
    Processing: Cpu,
    Cloud: Cloud,
    GPU: Database,
};

const GROUP_COLORS: Record<string, string> = {
    Paths: "var(--accent-cyan)",
    Processing: "var(--accent-violet)",
    Cloud: "var(--accent-primary)",
    GPU: "var(--accent-amber)",
};

export default function SettingsPage() {
    const { setPageTitle, theme } = useSystemStore();
    const queryClient = useQueryClient();
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    const [hoveredGroup, setHoveredGroup] = useState<string | null>(null);

    useEffect(() => { setPageTitle("Settings"); }, [setPageTitle]);

    const { data: settings, isLoading } = useQuery({
        queryKey: ["admin-settings"],
        queryFn: fetchSettings,
    });

    const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchHealth });
    const { data: gpu } = useQuery({ queryKey: ["admin-gpu"], queryFn: fetchGPUStatus });

    const [draft, setDraft] = useState<Record<string, string>>({});
    const [hasChanges, setHasChanges] = useState(false);
    const [focusedField, setFocusedField] = useState<SettingField | null>(null);
    const [leftScrolled, setLeftScrolled] = useState(false);
    const [rightScrolled, setRightScrolled] = useState(false);

    const handleLeftScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setLeftScrolled(e.currentTarget.scrollTop > 5);
    };
    const handleRightScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setRightScrolled(e.currentTarget.scrollTop > 5);
    };

    useEffect(() => {
        if (settings) {
            setDraft(settings);
            setHasChanges(false);
        }
    }, [settings]);

    const updateField = (key: string, value: string) => {
        setDraft((prev: Record<string, string>) => ({ ...prev, [key]: value }));
        setHasChanges(true);
    };

    const mutation = useMutation({
        mutationFn: (data: Record<string, string>) => updateSettings(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
            setHasChanges(false);
        },
    });

    const handleSave = () => { mutation.mutate(draft); };

    const groups = Array.from(new Set(SETTING_FIELDS.map((f) => f.group)));

    const scrollToSection = (group: string) => {
        const element = document.getElementById(`group-${group}`);
        if (element && scrollContainerRef.current) {
            scrollContainerRef.current.scrollTo({
                top: element.offsetTop - 12,
                behavior: "smooth"
            });
        }
    };

    const changedCount = Object.keys(draft).filter(k => draft[k] !== settings?.[k]).length;

    return (
        <div className="flex flex-row gap-6 h-full animate-fade-in w-full overflow-visible">
            {/* Left Column: Settings Content */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Scrollable Groups */}
                <div
                    ref={scrollContainerRef}
                    onScroll={handleLeftScroll}
                    className="flex-1 overflow-y-auto space-y-6 px-12 -mx-12 pr-4 -mr-4 scrollbar-premium transition-all duration-300 pt-4"
                    style={{
                        maskImage: leftScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none',
                        WebkitMaskImage: leftScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none'
                    }}
                >
                    {isLoading ? (
                        <div className="space-y-4">
                            {[1, 2, 3].map((i) => (
                                <div key={i} className="h-48 rounded-lg bg-elevated animate-pulse" />
                            ))}
                        </div>
                    ) : (
                        groups.map((group, gi) => {
                            const GroupIcon = GROUP_ICONS[group] || Settings;
                            const color = GROUP_COLORS[group];
                            const fields = SETTING_FIELDS.filter((f) => f.group === group);

                            return (
                                <motion.div
                                    key={group}
                                    id={`group-${group}`}
                                    className="card-base p-6"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.3, delay: gi * 0.05 }}
                                >
                                    <div className="flex items-center gap-2.5 mb-6 border-b border-muted/10 pb-3">
                                        <GroupIcon size={14} style={{ color }} />
                                        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-muted">
                                            {group} Configuration
                                        </h3>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                                        {fields.map((field) => (
                                            <div key={field.key} className="space-y-1.5 group">
                                                <label className="text-[11px] font-bold text-secondary group-focus-within:text-primary transition-colors">
                                                    {field.label}
                                                </label>

                                                {field.type === "boolean" ? (
                                                    <button
                                                        onMouseEnter={() => setFocusedField(field)}
                                                        onClick={() => updateField(field.key, draft[field.key] === "true" ? "false" : "true")}
                                                        className="flex items-center gap-3 w-full p-2.5 rounded-lg transition-all duration-200"
                                                        style={{
                                                            background: "rgba(128, 128, 128, 0.05)",
                                                            border: `1px solid ${draft[field.key] === "true" ? `${color}40` : "rgba(128, 128, 128, 0.1)"}`
                                                        }}
                                                    >
                                                        <div
                                                            className="w-8 h-4 rounded-full relative transition-colors duration-300"
                                                            style={{ background: draft[field.key] === "true" ? color : "rgba(128,128,128,0.2)" }}
                                                        >
                                                            <div
                                                                className="w-3 h-3 rounded-full bg-white absolute top-0.5 transition-all duration-300 shadow-sm"
                                                                style={{ left: draft[field.key] === "true" ? 18 : 2 }}
                                                            />
                                                        </div>
                                                        <span className="text-[12px] font-semibold" style={{ color: draft[field.key] === "true" ? color : "var(--text-secondary)" }}>
                                                            {draft[field.key] === "true" ? "Enabled" : "Disabled"}
                                                        </span>
                                                    </button>
                                                ) : field.type === "select" ? (
                                                    <select
                                                        onMouseEnter={() => setFocusedField(field)}
                                                        value={draft[field.key] || ""}
                                                        onChange={(e) => updateField(field.key, e.target.value)}
                                                        className="input-desktop"
                                                    >
                                                        {field.options?.map((opt) => (
                                                            <option key={opt} value={opt}>{opt}</option>
                                                        ))}
                                                    </select>
                                                ) : (
                                                    <input
                                                        onMouseEnter={() => setFocusedField(field)}
                                                        type={field.type === "number" ? "number" : "text"}
                                                        value={draft[field.key] || ""}
                                                        onChange={(e) => updateField(field.key, e.target.value)}
                                                        className="input-desktop font-mono"
                                                    />
                                                )}
                                                <p className="text-[10px] text-muted leading-tight">
                                                    {field.description}
                                                </p>
                                            </div>
                                        ))}
                                    </div>
                                </motion.div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Right Column: Control Rack */}
            <aside
                onScroll={handleRightScroll}
                className="w-72 flex-none hidden xl:flex flex-col gap-5 overflow-y-auto h-full px-10 -mx-10 pr-1 -mr-1 scrollbar-premium pb-8 transition-all duration-300 pt-3"
                style={{
                    maskImage: rightScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none',
                    WebkitMaskImage: rightScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none'
                }}
            >
                {/* Save Actions Card */}
                {hasChanges && (
                    <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="card-base p-5 border-emerald-500/20 shadow-lg shadow-emerald-500/10 bg-emerald-500/5"
                    >
                        <div className="text-[10px] font-bold uppercase tracking-widest mb-3 text-emerald-500 flex items-center justify-between">
                            Unsaved Draft
                            <Activity size={10} className="animate-pulse" />
                        </div>
                        <button
                            onClick={handleSave}
                            disabled={mutation.isPending}
                            className="btn-desktop btn-desktop-primary w-full h-11 flex items-center justify-center gap-2 text-[13px]"
                        >
                            {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                            Apply Changes
                        </button>
                    </motion.div>
                )}
                {/* Info Card (Contextual) */}
                <div className="card-base p-5 min-h-[165px] flex flex-col bg-elevated mt-2">
                    <div className="flex items-center gap-2 mb-3 text-muted uppercase tracking-widest text-[10px] font-bold">
                        <Info size={12} />
                        Field Guidance
                    </div>
                    <AnimatePresence mode="wait">
                        {focusedField ? (
                            <motion.div
                                key={focusedField.key}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="space-y-2"
                            >
                                <h4 className="text-[13px] font-bold text-primary">{focusedField.label}</h4>
                                <p className="text-[11px] leading-relaxed text-secondary">
                                    {focusedField.longDescription}
                                </p>
                            </motion.div>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center text-center opacity-30 mt-2">
                                <Activity size={20} className="text-muted" />
                                <p className="text-[10px] uppercase font-bold mt-2 text-muted">Focus field to see details</p>
                            </div>
                        )}
                    </AnimatePresence>
                </div>



                {/* Engine Diagnostics */}
                <div className="card-base p-5 shadow-sm">
                    <div className="text-[10px] font-bold uppercase tracking-widest mb-4 text-muted">Diagnostics</div>
                    <div className="space-y-3">
                        <DiagnosticRow label="FastAPI Hub" active={health?.status === "healthy"} icon={Activity} />
                        <DiagnosticRow label="NVIDIA CUDA" active={gpu?.gpu_found ?? false} icon={CpuIcon} color={GROUP_COLORS["GPU"]} />
                        <DiagnosticRow label="Sync Queue" active={draft["UPLOAD_QUEUE_ENABLED"] === "true"} icon={Cloud} color={GROUP_COLORS["Cloud"]} />
                    </div>

                    <div className="mt-5 pt-4 border-t border-muted/10 grid grid-cols-2 gap-2">
                        <div className="bg-elevated p-2 rounded">
                            <span className="block text-[9px] text-muted uppercase font-bold">Workers</span>
                            <span className="text-[11px] font-mono text-primary font-bold">{draft["WORKER_COUNT"]}</span>
                        </div>
                        <div className="bg-elevated p-2 rounded">
                            <span className="block text-[9px] text-muted uppercase font-bold">Log</span>
                            <span className="text-[11px] font-mono text-primary font-bold">{draft["LOG_LEVEL"]}</span>
                        </div>
                    </div>
                </div>

                {/* Secondary Actions */}
                <div className="pt-2">
                    <button
                        onClick={() => window.location.reload()}
                        className="w-full h-11 flex items-center justify-center gap-2 text-[11px] font-black uppercase tracking-widest rounded-full border border-slate-500/40 text-slate-600 dark:text-slate-400 bg-slate-500/20 hover:bg-rose-500 hover:border-rose-500 hover:text-white shadow-none hover:shadow-lg hover:shadow-rose-500/20 transition-all duration-300"
                    >
                        <RefreshCw size={15} />
                        Discard Draft
                    </button>
                </div>
            </aside>
        </div>
    );
}

function DiagnosticRow({ label, active, icon: Icon, color = "#10b981" }: { label: string; active: boolean; icon: any; color?: string }) {
    return (
        <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
                <Icon size={12} className="text-muted" />
                <span className="text-[11px] font-medium text-secondary">{label}</span>
            </div>
            <div
                className="w-2 h-2 rounded-full"
                style={{
                    background: active ? color : '#f43f5e',
                    boxShadow: active ? `0 0 10px ${color}30` : 'none',
                    border: `1px solid ${active ? 'transparent' : 'rgba(244, 63, 94, 0.2)'}`
                }}
            />
        </div>
    );
}
