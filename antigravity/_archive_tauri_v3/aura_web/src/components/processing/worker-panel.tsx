"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Moon,
    Radar,
    RefreshCw,
    Scissors,
    ScanFace,
    Dna,
    GitMerge,
    FolderInput,
    CloudUpload,
    Users,
} from "lucide-react";
import "./worker-animations.css";

// ---- Worker Action Definitions ----

interface WorkerAction {
    id: string;
    label: string;
    icon: typeof Moon;
    color: string;
    glowColor: string;
}

const WORKER_ACTIONS: WorkerAction[] = [
    { id: "idle",        label: "Idle",                icon: Moon,        color: "#64748B", glowColor: "rgba(100,116,139,0.15)" },
    { id: "scanning",    label: "Scanning Files",      icon: Radar,       color: "#06B6D4", glowColor: "rgba(6,182,212,0.18)" },
    { id: "normalizing", label: "Normalizing",         icon: RefreshCw,   color: "#8B5CF6", glowColor: "rgba(139,92,246,0.18)" },
    { id: "thumbnailing",label: "Thumbnailing",        icon: Scissors,    color: "#F59E0B", glowColor: "rgba(245,158,11,0.18)" },
    { id: "detecting",   label: "Detecting Faces",     icon: ScanFace,    color: "#22C55E", glowColor: "rgba(34,197,94,0.18)" },
    { id: "embedding",   label: "Extracting Vectors",  icon: Dna,         color: "#EC4899", glowColor: "rgba(236,72,153,0.18)" },
    { id: "clustering",  label: "Clustering",          icon: GitMerge,    color: "#6366F1", glowColor: "rgba(99,102,241,0.18)" },
    { id: "routing",     label: "Routing Photo",       icon: FolderInput, color: "#F97316", glowColor: "rgba(249,115,22,0.18)" },
    { id: "uploading",   label: "Cloud Upload",        icon: CloudUpload, color: "#0EA5E9", glowColor: "rgba(14,165,233,0.18)" },
];

const ACTIVE_ACTIONS = WORKER_ACTIONS.filter(a => a.id !== "idle");

// ---- Per-worker animation scenes (SVG-based) ----

function IdleScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            <div
                className="w-8 h-8 rounded-full"
                style={{
                    background: `${color}20`,
                    border: `1.5px solid ${color}40`,
                    animation: "worker-idle-breathe 3s ease-in-out infinite",
                }}
            />
            <span
                className="absolute text-[10px] font-bold"
                style={{
                    color,
                    top: "8px",
                    right: "12px",
                    animation: "worker-idle-z 2.5s ease-out infinite",
                }}
            >
                z
            </span>
            <span
                className="absolute text-[8px] font-bold"
                style={{
                    color,
                    top: "4px",
                    right: "6px",
                    animation: "worker-idle-z 2.5s ease-out 0.8s infinite",
                }}
            >
                z
            </span>
        </div>
    );
}

function ScanningScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            <div
                className="w-10 h-10 rounded-full"
                style={{ border: `1.5px dashed ${color}40` }}
            />
            <div
                className="absolute w-10 h-10 rounded-full"
                style={{
                    background: `conic-gradient(from 0deg, transparent 0%, ${color}30 30%, transparent 60%)`,
                    animation: "worker-scan-sweep 1.8s linear infinite",
                }}
            />
            <div
                className="absolute w-2 h-2 rounded-full"
                style={{ background: color }}
            />
            <div
                className="absolute w-6 h-6 rounded-full"
                style={{
                    border: `1px solid ${color}60`,
                    animation: "worker-scan-ping 1.5s ease-out infinite",
                }}
            />
        </div>
    );
}

function NormalizingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            <div
                className="w-8 h-8"
                style={{
                    background: `linear-gradient(135deg, ${color}30, ${color}60)`,
                    animation: "worker-normalize-morph 2.5s ease-in-out infinite",
                    border: `1.5px solid ${color}50`,
                }}
            />
        </div>
    );
}

function ThumbnailingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            <div
                className="w-10 h-10 rounded"
                style={{
                    background: `${color}15`,
                    border: `1.5px solid ${color}30`,
                    animation: "worker-thumb-crop 2.5s ease-in-out infinite",
                }}
            >
                <div
                    className="w-full h-full flex items-center justify-center"
                    style={{
                        background: `linear-gradient(45deg, ${color}20, ${color}40)`,
                        borderRadius: "2px",
                    }}
                />
            </div>
            <Scissors
                size={10}
                className="absolute"
                style={{
                    color,
                    bottom: "8px",
                    right: "10px",
                    animation: "worker-thumb-snip 1.5s ease-in-out infinite",
                }}
            />
        </div>
    );
}

function DetectingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
            {/* Face outline */}
            <div
                className="w-7 h-8 rounded-full"
                style={{ border: `1.5px solid ${color}40` }}
            />
            {/* Scan line */}
            <div
                className="absolute h-full w-3"
                style={{
                    background: `linear-gradient(90deg, transparent, ${color}40, transparent)`,
                    animation: "worker-detect-scan 2s ease-in-out infinite",
                }}
            />
            {/* Detection box */}
            <div
                className="absolute w-9 h-10 rounded"
                style={{
                    border: `1.5px solid ${color}`,
                    animation: "worker-detect-box 2s ease-in-out infinite",
                }}
            />
        </div>
    );
}

function EmbeddingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            <div className="flex items-center gap-0.5">
                {[0, 1, 2, 3, 4].map(i => (
                    <div
                        key={i}
                        className="w-1.5 h-1.5 rounded-full"
                        style={{
                            background: color,
                            animation: `worker-embed-dot 1.2s ease-out ${i * 0.2}s infinite`,
                        }}
                    />
                ))}
            </div>
            {/* Vector target */}
            <div
                className="absolute right-3 w-3 h-3 rounded-sm"
                style={{
                    background: `${color}30`,
                    border: `1px solid ${color}60`,
                    animation: "worker-embed-pulse 1.2s ease-in-out infinite",
                }}
            />
        </div>
    );
}

function ClusteringScene({ color }: { color: string }) {
    const positions = [
        { x: -10, y: -8 },
        { x: 10, y: -6 },
        { x: -6, y: 8 },
        { x: 8, y: 10 },
        { x: 0, y: -12 },
    ];
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            {positions.map((pos, i) => (
                <div
                    key={i}
                    className="absolute w-2 h-2 rounded-full"
                    style={{
                        background: color,
                        "--cx": `${pos.x}px`,
                        "--cy": `${pos.y}px`,
                        animation: `worker-cluster-gather 2.5s ease-in-out ${i * 0.3}s infinite`,
                    } as React.CSSProperties}
                />
            ))}
            {/* Center glow */}
            <div
                className="w-3 h-3 rounded-full"
                style={{
                    background: `${color}40`,
                    color,
                    animation: "worker-cluster-glow 2.5s ease-in-out infinite",
                }}
            />
        </div>
    );
}

function RoutingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            {/* Folder */}
            <div
                className="w-8 h-6 rounded-sm relative"
                style={{
                    background: `${color}20`,
                    border: `1.5px solid ${color}40`,
                    animation: "worker-route-folder 2s ease-in-out infinite",
                }}
            >
                <div
                    className="absolute -top-1.5 left-0.5 w-3 h-1.5 rounded-t-sm"
                    style={{ background: `${color}30`, borderTop: `1.5px solid ${color}40`, borderLeft: `1.5px solid ${color}40`, borderRight: `1.5px solid ${color}40` }}
                />
            </div>
            {/* File */}
            <div
                className="absolute w-3 h-4 rounded-sm"
                style={{
                    background: `${color}50`,
                    border: `1px solid ${color}`,
                    animation: "worker-route-slide 1.8s ease-in-out infinite",
                }}
            />
        </div>
    );
}

function UploadingScene({ color }: { color: string }) {
    return (
        <div className="relative w-full h-full flex items-center justify-center">
            {/* Cloud shape */}
            <div
                className="w-10 h-5 rounded-full"
                style={{
                    background: `${color}15`,
                    border: `1.5px solid ${color}30`,
                    animation: "worker-upload-cloud 2s ease-in-out infinite",
                }}
            />
            {/* Upload arrows */}
            {[0, 1, 2].map(i => (
                <div
                    key={i}
                    className="absolute w-0.5 h-3"
                    style={{
                        background: `linear-gradient(to top, transparent, ${color})`,
                        left: `calc(50% + ${(i - 1) * 6}px)`,
                        animation: `worker-upload-arrow 1.4s ease-out ${i * 0.3}s infinite`,
                    }}
                />
            ))}
        </div>
    );
}

const SCENE_MAP: Record<string, React.FC<{ color: string }>> = {
    idle: IdleScene,
    scanning: ScanningScene,
    normalizing: NormalizingScene,
    thumbnailing: ThumbnailingScene,
    detecting: DetectingScene,
    embedding: EmbeddingScene,
    clustering: ClusteringScene,
    routing: RoutingScene,
    uploading: UploadingScene,
};

// ---- WorkerAvatar ----

function WorkerAvatar({ 
    index, 
    isEngineRunning, 
    realTimeState,
    idPrefix = "worker-avatar"
}: { 
    index: number; 
    isEngineRunning: boolean;
    realTimeState: string | undefined;
    idPrefix?: string;
}) {
    // Determine current action. If idle/not provided, default to 'idle'
    // Map backend state to frontend action ID
    const rawState = realTimeState || "idle";
    
    // Ensure the state exists in our action list
    const action = WORKER_ACTIONS.find(a => a.id === rawState) || WORKER_ACTIONS[0];
    
    const ActionIcon = action.icon;
    const Scene = SCENE_MAP[action.id] || IdleScene;

    return (
        <motion.div
            id={`${idPrefix}-${index}`}
            className="flex flex-col items-center gap-2"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.08 }}
        >
            {/* Avatar circle */}
            <div
                className="relative w-14 h-14 rounded-2xl flex items-center justify-center transition-all duration-700"
                style={{
                    background: action.id !== "idle" ? `${action.color}15` : "rgba(255,255,255,0.03)",
                    border: `1.5px solid ${action.id !== "idle" ? action.color : "rgba(255,255,255,0.1)"}`,
                    boxShadow: action.id !== "idle" 
                        ? `0 0 30px ${action.glowColor}, inset 0 0 12px ${action.glowColor}` 
                        : "none",
                }}
            >
                <Scene color={action.color} />

                {/* Worker number badge */}
                <div
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black"
                    style={{
                        background: "var(--bg-card)",
                        border: `1.5px solid ${action.color}40`,
                        color: action.color,
                    }}
                >
                    {index + 1}
                </div>
            </div>

            {/* Action label */}
            <AnimatePresence mode="wait">
                <motion.div
                    key={action.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.25 }}
                    className="flex flex-col items-center gap-0.5"
                >
                    <div className="flex items-center gap-1">
                        <ActionIcon
                            size={9}
                            style={{ color: action.color }}
                        />
                        <span
                            className="text-[9px] font-bold uppercase tracking-wider"
                            style={{ color: action.color }}
                        >
                            {action.label}
                        </span>
                    </div>
                </motion.div>
            </AnimatePresence>
        </motion.div>
    );
}

// ---- WorkerPanel (exported) ----

interface WorkerPanelProps {
    workerCount: number;
    isEngineRunning: boolean;
    workerStates?: Record<string, string>;
    title?: string;
    idPrefix?: string;
}

export function WorkerPanel({ 
    workerCount, 
    isEngineRunning, 
    workerStates = {}, 
    title = "Worker Pool", 
    idPrefix = "worker-avatar" 
}: WorkerPanelProps) {
    const threadNames = Object.keys(workerStates).sort();
    
    // Include both processing and upload workers in the count (cap at 16 to avoid layout issues)
    const count = Math.max(1, Math.min(Math.max(workerCount, threadNames.length), 16));

    return (
        <motion.div
            className="card-base p-3 h-full flex flex-col min-w-[280px]"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
        >
            {/* Header */}
            <div className="flex items-center gap-2 mb-2">
                <Users size={14} style={{ color: "var(--accent-violet)" }} />
                <h3
                    className="text-[11px] font-semibold uppercase tracking-widest"
                    style={{ color: "var(--text-tertiary)" }}
                >
                    {title}
                </h3>
                <div className="ml-auto">
                    <span
                        className={`badge ${isEngineRunning ? "badge-success" : "badge-info"}`}
                    >
                        <div
                            className="w-1.5 h-1.5 rounded-full"
                            style={{
                                background: isEngineRunning ? "#22C55E" : "#64748B",
                                boxShadow: isEngineRunning ? "0 0 6px rgba(34,197,94,0.5)" : "none",
                            }}
                        />
                        {isEngineRunning ? "Active" : "Idle"}
                    </span>
                </div>
            </div>

            {/* Workers grid */}
            <div className="flex-1 flex items-start justify-center">
                <div
                    className="grid gap-4"
                    style={{
                        gridTemplateColumns: count <= 2 ? "repeat(1, 1fr)" : count <= 6 ? "repeat(2, 1fr)" : "repeat(3, 1fr)",
                    }}
                >
                    {Array.from({ length: count }).map((_, i) => (
                        <WorkerAvatar
                            key={i}
                            index={i}
                            isEngineRunning={isEngineRunning}
                            realTimeState={workerStates[threadNames[i]]}
                            idPrefix={idPrefix}
                        />
                    ))}
                </div>
            </div>
        </motion.div>
    );
}
