"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { WorkerPanel } from "@/components/processing/worker-panel";

// --- TYPES & HOOKS ---

type Coordinates = { x: number; y: number };

// A hook to dynamically track the center coordinates of DOM elements by ID
function useElementCoordinates(ids: string[], containerRef: React.RefObject<HTMLElement | null>) {
    const [coords, setCoords] = useState<Record<string, Coordinates>>({});
    
    // Stable string representation of IDs to prevent infinite loops
    const idsString = ids.join(',');

    const updateCoords = useCallback(() => {
        if (!containerRef.current) return;
        const containerRect = containerRef.current.getBoundingClientRect();
        const idList = idsString.split(',').filter(Boolean);

        setCoords((prev) => {
            const newCoords: Record<string, Coordinates> = {};
            let changed = false;

            idList.forEach((id) => {
                const el = document.getElementById(id);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    // Calculate center relative to the container
                    const x = rect.left - containerRect.left + rect.width / 2;
                    const y = rect.top - containerRect.top + rect.height / 2;
                    newCoords[id] = { x, y };

                    if (!prev[id] || prev[id].x !== x || prev[id].y !== y) {
                        changed = true;
                    }
                }
            });

            if (!changed && Object.keys(prev).length !== Object.keys(newCoords).length) {
                changed = true;
            }

            return changed ? newCoords : prev;
        });
    }, [idsString, containerRef]);

    useEffect(() => {
        updateCoords();
        window.addEventListener("resize", updateCoords);
        window.addEventListener("scroll", updateCoords, true); // Catch scroll events

        let observer: MutationObserver | null = null;
        if (containerRef.current) {
            observer = new MutationObserver(updateCoords);
            observer.observe(containerRef.current, { childList: true, subtree: true, attributes: true });
        }

        return () => {
            window.removeEventListener("resize", updateCoords);
            window.removeEventListener("scroll", updateCoords, true);
            if (observer) observer.disconnect();
        };
    }, [updateCoords, containerRef]);

    return coords;
}

// Generates a smooth horizontal "S" curve between two points
function generateBezierCurve(start: Coordinates, end: Coordinates, curvature = 0.5) {
    const dx = Math.abs(end.x - start.x);
    // Control points are pushed out horizontally based on the distance
    const cx1 = start.x + dx * curvature;
    const cy1 = start.y;
    const cx2 = end.x - dx * curvature;
    const cy2 = end.y;
    return `M ${start.x} ${start.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${end.x} ${end.y}`;
}

// --- CINEMATIC PULSE COMPONENT ---

interface PulseProps {
    pathD: string;
    color: string;
    duration: number;
    delay?: number;
    onComplete: () => void;
}

function CinematicPulse({ pathD, color, duration, delay = 0, onComplete }: PulseProps) {
    const pathRef = useRef<SVGPathElement>(null);
    const [pathLength, setPathLength] = useState(1000);

    useEffect(() => {
        if (pathRef.current) {
            setPathLength(pathRef.current.getTotalLength());
        }
    }, [pathD]);

    // A streak is a segment of the stroke. We make it 15% of the total path length.
    const streakLength = pathLength * 0.15;

    return (
        <motion.g
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 1, 0] }}
            transition={{ duration: duration, delay, times: [0, 0.1, 0.9, 1] }}
            onAnimationComplete={onComplete}
        >
            {/* The hidden path used purely to measure length (if needed by browser) */}
            <path ref={pathRef} d={pathD} fill="none" stroke="transparent" />

            {/* Core Energy Beam */}
            <motion.path
                d={pathD}
                fill="none"
                stroke={color}
                strokeWidth={3}
                strokeLinecap="round"
                strokeDasharray={`${streakLength} ${pathLength}`}
                initial={{ strokeDashoffset: pathLength }}
                animate={{ strokeDashoffset: -streakLength }}
                transition={{ duration: duration, delay, ease: "easeInOut" }}
                style={{ filter: "url(#glow-core)" }}
            />

            {/* Ambient Outer Bloom */}
            <motion.path
                d={pathD}
                fill="none"
                stroke={color}
                strokeWidth={8}
                strokeLinecap="round"
                strokeDasharray={`${streakLength * 1.2} ${pathLength}`}
                initial={{ strokeDashoffset: pathLength }}
                animate={{ strokeDashoffset: -streakLength * 1.2 }}
                transition={{ duration: duration, delay, ease: "easeInOut" }}
                style={{ filter: "url(#glow-ambient)", opacity: 0.5 }}
            />
        </motion.g>
    );
}

// --- MAIN PIPELINE WRAPPER ---

interface PipelineProps {
    isEngineRunning: boolean;
    workerCount: number;
    processingStates: Record<string, string>;
    uploadStates: Record<string, string>;
    stats?: any;
}

export function DataFlowPipeline({ isEngineRunning, workerCount, processingStates, uploadStates, stats }: PipelineProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    
    // Processing pool count
    const pCount = Math.max(1, Math.min(Math.max(workerCount, Object.keys(processingStates).length), 16));
    // Upload pool count
    const uCount = Math.max(1, Math.min(Math.max(2, Object.keys(uploadStates).length), 16));

    const processingIds = Array.from({ length: pCount }).map((_, i) => `worker-avatar-${i}`);
    const uploadIds = Array.from({ length: uCount }).map((_, i) => `upload-avatar-${i}`);
    
    const nodeIds = ["node-incoming", "node-local", "node-cloud", ...processingIds, ...uploadIds];
    const coords = useElementCoordinates(nodeIds, containerRef);

    // State to hold active pulses
    const [pulses, setPulses] = useState<Array<{ id: string; type: string; workerId: string; color: string }>>([]);
    const prevStatesRef = useRef<Record<string, string>>({});
    
    // --- SENDER-SIDE ACCOUNTING ---
    // We track how many pulses have been "dispatched" from each sender node globally.
    // This ensures that even if workers flicker, we only send as many rays as there are files.
    const dispatchedIncomingCount = useRef(0);
    const dispatchedWorkerCount = useRef(0);
    const lastPendingCount = useRef<number | null>(null);
    const lastProcessedTotal = useRef<number | null>(null);

    // Track which workers are currently "carrying" a packet (to avoid multiple rays to/from the same busy worker)
    const workerAssignments = useRef<Record<string, boolean>>({});

    useEffect(() => {
        if (!stats) return;

        const photosByStatus = stats.photos_by_status || {};
        const totalPhotos = stats.total_photos || 0;
        const pendingCount = photosByStatus["pending"] ?? totalPhotos;
        
        // Count everything that has passed the first processing stage
        const processedTotal = (photosByStatus["completed"] || 0) + 
                             (photosByStatus["error"] || 0) + 
                             (photosByStatus["no_faces"] || 0);

        // 1. DISPATCH FROM INCOMING (Sender Side)
        // If pending count decreased, a file was sent from Incoming to a Worker.
        const photosSentFromIncoming = totalPhotos - pendingCount;
        if (photosSentFromIncoming > dispatchedIncomingCount.current) {
            const numToDispatch = photosSentFromIncoming - dispatchedIncomingCount.current;
            
            // Find workers that just became busy and aren't assigned yet
            const pThreadNames = Object.keys(processingStates).sort();
            let dispatchedThisCycle = 0;

            pThreadNames.forEach((threadName, index) => {
                if (dispatchedThisCycle < numToDispatch) {
                    const workerId = `worker-avatar-${index}`;
                    const state = processingStates[threadName];
                    const isActive = ["scanning", "normalizing", "thumbnailing", "detecting", "embedding"].includes(state);
                    
                    if (isActive && !workerAssignments.current[workerId]) {
                        spawnPulse("incoming_to_worker", workerId, "#f59e0b");
                        workerAssignments.current[workerId] = true;
                        dispatchedIncomingCount.current++;
                        dispatchedThisCycle++;
                    }
                }
            });
        }

        // 2. DISPATCH FROM WORKER TO LOCAL (Sender Side)
        // If the total processed/completed count increased, a file left the worker pool.
        if (processedTotal > dispatchedWorkerCount.current) {
            const numToReturn = processedTotal - dispatchedWorkerCount.current;
            
            // Find workers that are in an "end-of-cycle" state or just went idle and were busy
            const pThreadNames = Object.keys(processingStates).sort();
            let returnedThisCycle = 0;

            pThreadNames.forEach((threadName, index) => {
                const workerId = `worker-avatar-${index}`;
                const state = processingStates[threadName];
                const isFinishing = ["routing", "clustering"].includes(state);
                const wentIdle = (state === "idle" || !state);

                if (returnedThisCycle < numToReturn && workerAssignments.current[workerId]) {
                    if (isFinishing || wentIdle) {
                        spawnPulse("worker_to_local", workerId, "#10b981");
                        workerAssignments.current[workerId] = false;
                        dispatchedWorkerCount.current++;
                        returnedThisCycle++;
                    }
                }
            });
            
            // Safety: if counts increased but no specific worker matched (e.g. state missed), just sync the count
            if (returnedThisCycle < numToReturn) {
                dispatchedWorkerCount.current = processedTotal;
            }
        }

        // 3. UPLODER DISPATCH (Fallback to state-sensing as there's no global uploader count in stats yet)
        const uThreadNames = Object.keys(uploadStates).sort();
        uThreadNames.forEach((threadName, index) => {
            const currentState = uploadStates[threadName];
            const prevState = prevStatesRef.current[threadName] || "idle";
            const workerId = `upload-avatar-${index}`;
            
            if (currentState !== prevState) {
                if (currentState === "uploading" && !workerAssignments.current[workerId]) {
                    spawnPulse("local_to_upload", workerId, "#06b6d4");
                    workerAssignments.current[workerId] = true;
                }
                if (currentState === "idle" && prevState === "uploading" && workerAssignments.current[workerId]) {
                    spawnPulse("upload_to_cloud", workerId, "#8b5cf6");
                    workerAssignments.current[workerId] = false;
                }
            }
        });

        prevStatesRef.current = { ...processingStates, ...uploadStates };
    }, [processingStates, uploadStates, stats]);

    const spawnPulse = (type: string, workerId: string, color: string) => {
        const id = `${Date.now()}-${Math.random()}`;
        setPulses((prev) => [...prev, { id, type, workerId, color }]);
    };

    const removePulse = (id: string) => {
        setPulses((prev) => prev.filter((p) => p.id !== id));
    };

    const isProcessingActive = Object.values(processingStates).some(s => s !== "idle");
    const isUploadingActive = Object.values(uploadStates).some(s => s !== "idle");

    return (
        <div ref={containerRef} className="relative w-full h-full flex items-center justify-between px-6 py-2 gap-4 overflow-hidden">
            
            {/* SVG OVERLAY - THE MAGIC HAPPENS HERE */}
            <svg
                className="pointer-events-none absolute inset-0 w-full h-full z-50"
                style={{ filter: "drop-shadow(0 0 10px rgba(0,0,0,0.5))" }}
            >
                <defs>
                    {/* Cinematic Bloom Filters */}
                    <filter id="glow-core" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur stdDeviation="2" result="blur" />
                        <feMerge>
                            <feMergeNode in="blur" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>
                    <filter id="glow-ambient" x="-50%" y="-50%" width="200%" height="200%">
                        <feGaussianBlur stdDeviation="8" result="blur" />
                        <feMerge>
                            <feMergeNode in="blur" />
                            <feMergeNode in="SourceGraphic" />
                        </feMerge>
                    </filter>
                </defs>

                {/* Base Spline Connectors (Dimmed background tracks) */}
                <g stroke="rgba(255,255,255,0.05)" strokeWidth={1} fill="none">
                    {processingIds.map(wId => coords["node-incoming"] && coords[wId] && <path key={`track-in-${wId}`} d={generateBezierCurve(coords["node-incoming"], coords[wId])} />)}
                    {processingIds.map(wId => coords[wId] && coords["node-local"] && <path key={`track-loc-${wId}`} d={generateBezierCurve(coords[wId], coords["node-local"])} />)}
                    {uploadIds.map(wId => coords["node-local"] && coords[wId] && <path key={`track-uloc-${wId}`} d={generateBezierCurve(coords["node-local"], coords[wId])} />)}
                    {uploadIds.map(wId => coords[wId] && coords["node-cloud"] && <path key={`track-cld-${wId}`} d={generateBezierCurve(coords[wId], coords["node-cloud"])} />)}
                </g>

                {/* Active Pulses */}
                <AnimatePresence>
                    {pulses.map((pulse) => {
                        let start, end;
                        const worker = coords[pulse.workerId];
                        const incoming = coords["node-incoming"];
                        const local = coords["node-local"];
                        const cloud = coords["node-cloud"];

                        if (!worker || !incoming || !local || !cloud) return null;

                        if (pulse.type === "incoming_to_worker") {
                            start = incoming; end = worker;
                        } else if (pulse.type === "worker_to_local") {
                            start = worker; end = local;
                        } else if (pulse.type === "local_to_upload") {
                            start = local; end = worker;
                        } else if (pulse.type === "upload_to_cloud") {
                            start = worker; end = cloud;
                        }

                        if (!start || !end) return null;

                        return (
                            <CinematicPulse
                                key={pulse.id}
                                pathD={generateBezierCurve(start, end)}
                                color={pulse.color}
                                duration={2.2}
                                onComplete={() => removePulse(pulse.id)}
                            />
                        );
                    })}
                </AnimatePresence>
            </svg>

            {/* 1. INCOMING NODE */}
            <div id="node-incoming" className="w-20 xl:w-24 h-[220px] flex-none relative z-10 transition-all duration-700">
                <div 
                    className="card-base w-full h-full p-4 flex flex-col items-center justify-between bg-black/40 backdrop-blur-xl border border-white/10 relative overflow-hidden group"
                    style={{
                        borderColor: isProcessingActive ? "rgba(245, 158, 11, 0.4)" : "rgba(255, 255, 255, 0.1)",
                        boxShadow: isProcessingActive ? "0 0 30px rgba(245, 158, 11, 0.15)" : "none"
                    }}
                >
                    <div className={`absolute inset-0 bg-gradient-to-t from-amber-500/10 to-transparent transition-opacity duration-700 ${isProcessingActive ? 'opacity-100' : 'opacity-0'}`} />
                    <h2 
                        className="font-bold tracking-widest text-[10px] xl:text-xs uppercase [writing-mode:vertical-lr] rotate-180 transition-all duration-700"
                        style={{ 
                            color: isProcessingActive ? "#f59e0b" : "var(--text-muted)",
                            textShadow: isProcessingActive ? "0 0 8px rgba(245,158,11,0.5)" : "none"
                        }}
                    >
                        Incoming
                    </h2>
                    <div className="flex flex-col gap-3">
                        <div className={`w-2 h-2 rounded-full transition-all duration-700 ${isProcessingActive ? 'bg-amber-500 animate-pulse' : 'bg-white/10'}`} style={{ animationDelay: "0ms" }} />
                        <div className={`w-2 h-2 rounded-full transition-all duration-700 ${isProcessingActive ? 'bg-amber-500 animate-pulse' : 'bg-white/10'}`} style={{ animationDelay: "200ms" }} />
                        <div className={`w-2 h-2 rounded-full transition-all duration-700 ${isProcessingActive ? 'bg-amber-500 animate-pulse' : 'bg-white/10'}`} style={{ animationDelay: "400ms" }} />
                    </div>
                </div>
            </div>

            {/* 2. PROCESSING POOL */}
            <div className="flex-1 relative z-10 flex justify-center max-w-[320px]">
                <div className="w-full shadow-[0_0_30px_rgba(0,0,0,0.5)] rounded-2xl border border-white/5 bg-black/20 backdrop-blur-3xl">
                    <WorkerPanel 
                        title="Processing Pool"
                        idPrefix="worker-avatar"
                        workerCount={workerCount} 
                        isEngineRunning={isEngineRunning} 
                        workerStates={processingStates}
                    />
                </div>
            </div>

            {/* 3. LOCAL STORAGE */}
            <div id="node-local" className="w-20 xl:w-24 h-[220px] flex-none relative z-10 transition-all duration-700">
                <div 
                    className="card-base w-full h-full p-4 flex flex-col items-center justify-between bg-black/40 backdrop-blur-xl border border-emerald-500/20"
                    style={{
                        borderColor: (isProcessingActive || isUploadingActive) ? "rgba(16, 185, 129, 0.4)" : "rgba(16, 185, 129, 0.1)",
                        boxShadow: (isProcessingActive || isUploadingActive) ? "0 0 30px rgba(16, 185, 129, 0.15)" : "none"
                    }}
                >
                    <h2 
                        className="font-bold tracking-widest text-[10px] xl:text-xs uppercase [writing-mode:vertical-lr] rotate-180 transition-all duration-700"
                        style={{ 
                            color: (isProcessingActive || isUploadingActive) ? "#34d399" : "var(--text-muted)",
                            textShadow: (isProcessingActive || isUploadingActive) ? "0 0 8px rgba(16,185,129,0.5)" : "none"
                        }}
                    >
                        Local DB
                    </h2>
                    <div className="w-4 h-20 flex flex-col gap-1 rounded overflow-hidden bg-white/5">
                        <div className={`flex-1 transition-all duration-700 ${(isProcessingActive || isUploadingActive) ? 'bg-emerald-500/40 animate-pulse' : 'bg-emerald-500/10'}`} />
                        <div className={`flex-1 transition-all duration-700 ${(isProcessingActive || isUploadingActive) ? 'bg-emerald-500/20' : 'bg-emerald-500/5'}`} />
                        <div className={`flex-1 transition-all duration-700 ${(isProcessingActive || isUploadingActive) ? 'bg-emerald-500/30' : 'bg-emerald-500/5'}`} />
                    </div>
                </div>
            </div>

            {/* 4. UPLOAD POOL */}
            <div className="flex-1 relative z-10 flex justify-center max-w-[280px]">
                <div className="w-full shadow-[0_0_30px_rgba(0,0,0,0.5)] rounded-2xl border border-white/5 bg-black/20 backdrop-blur-3xl">
                    <WorkerPanel 
                        title="Upload Pool"
                        idPrefix="upload-avatar"
                        workerCount={Math.max(2, Object.keys(uploadStates).length)} 
                        isEngineRunning={isEngineRunning} 
                        workerStates={uploadStates}
                    />
                </div>
            </div>

            {/* 5. CLOUD STORAGE */}
            <div id="node-cloud" className="w-20 xl:w-24 h-[220px] flex-none relative z-10 transition-all duration-700">
                <div 
                    className="card-base w-full h-full p-4 flex flex-col items-center justify-between bg-black/40 backdrop-blur-xl border border-violet-500/20"
                    style={{
                        borderColor: isUploadingActive ? "rgba(139, 92, 246, 0.4)" : "rgba(139, 92, 246, 0.1)",
                        boxShadow: isUploadingActive ? "0 0 30px rgba(139, 92, 246, 0.15)" : "none"
                    }}
                >
                    <h2 
                        className="font-bold tracking-widest text-[10px] xl:text-xs uppercase [writing-mode:vertical-lr] rotate-180 transition-all duration-700"
                        style={{ 
                            color: isUploadingActive ? "#a78bfa" : "var(--text-muted)",
                            textShadow: isUploadingActive ? "0 0 8px rgba(139,92,246,0.5)" : "none"
                        }}
                    >
                        Cloud
                    </h2>
                    <div className="flex items-center justify-center relative">
                        <div className={`absolute inset-0 transition-all duration-700 blur-xl rounded-full ${isUploadingActive ? 'bg-violet-500/30 scale-125' : 'bg-violet-500/0 scale-0'}`} />
                        <svg 
                            className={`w-8 h-8 transition-all duration-700 relative z-10 ${isUploadingActive ? 'text-violet-400 scale-110' : 'text-white/20'}`} 
                            fill="none" 
                            viewBox="0 0 24 24" 
                            stroke="currentColor"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                        </svg>
                    </div>
                </div>
            </div>
        </div>
    );
}
