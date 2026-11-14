"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
    LayoutDashboard,
    Users,
    Target,
    Cloud,
    MessageCircle,
    HeartPulse,
    Settings,
} from "lucide-react";

const navItems = [
    { href: "/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/people", label: "People", icon: Users },
    { href: "/processing", label: "Processing", icon: Target },
    { href: "/cloud", label: "Cloud Sync", icon: Cloud },
    { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
    { href: "/health", label: "Health", icon: HeartPulse },
    { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="fixed left-0 top-0 h-screen w-[80px] flex flex-col items-center z-50 sidebar-container">
            {/* Logo Section */}
            <div className="pt-8 pb-4">
                <Link href="/">
                    <motion.div
                        className="w-12 h-12 flex items-center justify-center relative group"
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                    >
                        <Image 
                            src="/logo.png"
                            alt="AURA Logo"
                            width={44}
                            height={44}
                            className="object-contain"
                            priority
                        />
                    </motion.div>
                </Link>
            </div>

            {/* Navigation Items (Centered) */}
            <div className="flex-1 flex flex-col justify-center pb-12">
                <div className="flex flex-col gap-6">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link key={item.href} href={item.href}>
                                <div className="relative flex items-center justify-center">
                                    {/* 7-Layer Possessed Dark Magic Smoke */}
                                    {isActive && (
                                        <div className="aurora-ghost-smoke">
                                            <div className="smoke-l7" /> {/* Deep dark veil — bottom */}
                                            <div className="smoke-l1" /> {/* Slow base shroud */}
                                            <div className="smoke-l5" /> {/* Ghost wisp B — dark underside */}
                                            <div className="smoke-l3" /> {/* Counter-tendril */}
                                            <div className="smoke-l4" /> {/* Ghost wisp A */}
                                            <div className="smoke-l2" /> {/* Primary tendril — top */}
                                            <div className="smoke-l6" /> {/* Possessed core glow */}
                                            <div className="smoke-wisp" /> {/* Escaping micro wisp */}
                                        </div>
                                    )}
                                    
                                    <motion.div
                                        className={`icon-circle relative z-10 ${isActive ? 'bg-emerald-500/10' : ''}`}
                                        whileHover={{ scale: 1.1 }}
                                        whileTap={{ scale: 0.9 }}
                                        title={item.label}
                                        style={isActive ? { boxShadow: "0 0 18px rgba(16, 185, 129, 0.25), 0 0 6px rgba(16,185,129,0.15) inset" } : {}}
                                    >
                                        <item.icon 
                                            size={20} 
                                            className={isActive ? "text-emerald-400 drop-shadow-[0_0_6px_rgba(16,200,140,0.7)]" : "text-primary"} 
                                            strokeWidth={isActive ? 2.5 : 2}
                                            fill="currentColor"
                                        />
                                    </motion.div>
                                </div>
                            </Link>
                        );
                    })}
                </div>
            </div>
        </aside>
    );
}
