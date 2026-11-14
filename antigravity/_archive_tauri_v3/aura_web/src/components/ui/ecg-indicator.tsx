"use client";

import { motion } from "framer-motion";

interface ECGIndicatorProps {
    active: boolean;
    width?: number;
    height?: number;
    color?: string;
}

export function ECGIndicator({ active, width = 120, height = 40, color = "#4BA8FF" }: ECGIndicatorProps) {
    // A more realistic ECG wave 
    const ecgPath = "M 0 20 L 15 20 L 20 15 L 25 25 L 30 20 L 35 20 L 40 5 L 45 35 L 50 20 L 60 20 L 65 15 L 70 20 L 100 20";
    const flatPath = "M 0 20 L 100 20";

    return (
        <div className="relative group" style={{ width, height }}>
            <div 
                className="relative w-full h-full flex items-center justify-center transition-all duration-300 transform-gpu"
                style={{ 
                    background: "transparent",
                    boxShadow: "none",
                    backdropFilter: "none",
                }}
            >

                <svg 
                    viewBox="0 0 100 40" 
                    className="w-full h-full pointer-events-none"
                    preserveAspectRatio="none"
                    style={{ 
                        filter: active 
                            ? `drop-shadow(0 0 8px ${color}) drop-shadow(0 0 2px white)` 
                            : "none" 
                    }}
                >
                    {/* The "Phosphor" Glow Trace - Static path with scanning mask */}
                    <defs>
                        <linearGradient id="scanGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="white" stopOpacity="0" />
                            <stop offset="40%" stopColor="white" stopOpacity="0.1" />
                            <stop offset="90%" stopColor="white" stopOpacity="1" />
                            <stop offset="100%" stopColor="white" stopOpacity="0" />
                        </linearGradient>
                        <mask id="scanMask">
                            <motion.rect
                                x="-40"
                                y="0"
                                width="40"
                                height="40"
                                fill="url(#scanGradient)"
                                animate={active ? {
                                    x: [-40, 140]
                                } : { x: -40 }}
                                transition={{
                                    duration: 2,
                                    repeat: Infinity,
                                    ease: "linear"
                                }}
                            />
                        </mask>
                    </defs>

                    {/* Scanning Trace (Animated/Brighter) */}
                    <motion.path
                        d={active ? ecgPath : flatPath}
                        fill="none"
                        stroke={active ? color : "var(--text-muted)"}
                        strokeWidth="3.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        mask={active ? "url(#scanMask)" : undefined}
                    />
                </svg>
            </div>
        </div>
    );
}
