"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
    Users,
    Search,
    UserCheck,
    Camera,
    UsersRound,
    Filter,
    FolderOpen,
    Cloud,
    X,
    Loader2
} from "lucide-react";
import { fetchPersons, type PersonItem } from "@/lib/api";
import { openLocalPersonFolder, getPersonCloudUrl } from "@/lib/api";
import { useSystemStore } from "@/lib/store";

export default function PeoplePage() {
    const setPageTitle = useSystemStore((s) => s.setPageTitle);
    const [search, setSearch] = useState("");
    const [showEnrolledOnly, setShowEnrolledOnly] = useState(false);
    const [isScrolled, setIsScrolled] = useState(false);
    const [selectedPerson, setSelectedPerson] = useState<PersonItem | null>(null);

    const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
        setIsScrolled(e.currentTarget.scrollTop > 5);
    };

    useEffect(() => {
        setPageTitle("People");
    }, [setPageTitle]);

    const { data: persons, isLoading } = useQuery({
        queryKey: ["persons"],
        queryFn: fetchPersons,
        refetchInterval: 10_000,
    });

    const filtered = (persons ?? []).filter((p) => {
        const matchesSearch =
            p.name.toLowerCase().includes(search.toLowerCase()) ||
            (p.enrolled_name?.toLowerCase().includes(search.toLowerCase()) ??
                false);
        const matchesFilter = showEnrolledOnly ? p.enrolled : true;
        return matchesSearch && matchesFilter;
    });

    const enrolledCount = (persons ?? []).filter((p) => p.enrolled).length;

    return (
        <div className="flex flex-col h-full space-y-4 animate-fade-in">
            {/* Toolbar */}
            <div className="flex-none flex items-center gap-3 flex-wrap">
                {/* Search */}
                <div className="relative flex-1 max-w-sm">
                    <Search
                        size={16}
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
                    />
                    <input
                        type="text"
                        placeholder="Search by name..."
                        className="w-full pl-10 pr-4 py-2 text-[13px] border border-muted/10 bg-elevated rounded-xl focus:outline-none focus:ring-1 focus:ring-accent-primary text-primary"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                {/* Filter toggle */}
                <button
                    onClick={() => setShowEnrolledOnly(!showEnrolledOnly)}
                    className="btn-desktop"
                    style={{
                        background: showEnrolledOnly
                            ? "var(--accent-primary-dim)"
                            : undefined,
                        color: showEnrolledOnly
                            ? "var(--accent-primary)"
                            : undefined,
                        borderColor: showEnrolledOnly
                            ? "rgba(34, 197, 94, 0.2)"
                            : undefined,
                    }}
                >
                    <Filter size={13} />
                    Enrolled Only
                </button>

                {/* Count */}
                <span
                    className="text-[12px] ml-auto"
                    style={{ color: "var(--text-muted)" }}
                >
                    {filtered.length} of {persons?.length ?? 0} people ·{" "}
                    {enrolledCount} enrolled
                </span>
            </div>

            {/* Scrollable Content */}
            <div
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto px-10 -mx-10 scrollbar-premium transition-all duration-300"
                style={{
                    maskImage: isScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none',
                    WebkitMaskImage: isScrolled ? 'linear-gradient(to bottom, transparent, black 15px)' : 'none'
                }}
            >
                {/* Grid */}
                {isLoading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {Array.from({ length: 8 }).map((_, i) => (
                            <div
                                key={i}
                                className="card-base animate-shimmer"
                                style={{ height: 140 }}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        <AnimatePresence>
                            {filtered.map((person, idx) => (
                                <PersonCard
                                    key={person.id}
                                    person={person}
                                    index={idx}
                                    onSelect={setSelectedPerson}
                                />
                            ))}
                        </AnimatePresence>
                    </div>
                )}

                {!isLoading && filtered.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <Users
                            size={40}
                            style={{ color: "var(--text-muted)" }}
                            strokeWidth={1.5}
                        />
                        <p
                            className="mt-3 text-[14px] font-medium"
                            style={{ color: "var(--text-secondary)" }}
                        >
                            No people found
                        </p>
                        <p
                            className="text-[12px] mt-1"
                            style={{ color: "var(--text-muted)" }}
                        >
                            {search
                                ? "Try a different search term"
                                : "People will appear here once photos are processed"}
                        </p>
                    </div>
                )}
            </div>

            <AnimatePresence>
                {selectedPerson && (
                    <>
                        {/* Independent Backdrop with Post-Exit Linger */}
                        <motion.div
                            key="modal-backdrop"
                            initial={{ opacity: 0, backdropFilter: "blur(0px)" }}
                            animate={{ opacity: 1, backdropFilter: "blur(40px)" }}
                            exit={{
                                opacity: 0,
                                backdropFilter: "blur(0px)",
                                transition: { duration: 1, delay: 0.1, ease: "easeInOut" }
                            }}
                            className="fixed inset-0 z-[90]"
                            style={{ background: "rgba(0, 0, 0, 0.5)" }}
                            onClick={() => setSelectedPerson(null)}
                        />

                        {/* Modal Content - Centered Layer */}
                        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 pointer-events-none">
                            <PersonDetailsModal
                                person={selectedPerson}
                                onClose={() => setSelectedPerson(null)}
                            />
                        </div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
}

const getThumbnailUrl = (person: PersonItem) => {
    if (!person.representative_photo) return "";
    let url = `/api/thumbnail?path=${encodeURIComponent(person.representative_photo)}`;
    if (person.face_bbox) {
        url += `&x=${person.face_bbox.x}&y=${person.face_bbox.y}&w=${person.face_bbox.w}&h=${person.face_bbox.h}`;
    }
    return url;
};

function PersonCard({
    person,
    index,
    onSelect,
}: {
    person: PersonItem;
    index: number;
    onSelect: (p: PersonItem) => void;
}) {
    const displayName = person.enrolled_name ?? person.name;
    const initials = displayName
        .split(/[_\s]+/)
        .map((w) => w[0]?.toUpperCase())
        .slice(0, 2)
        .join("");

    return (
        <motion.div
            layoutId={`card-${person.id}`}
            className="card-base p-4 flex flex-col gap-2.5 relative overflow-hidden cursor-pointer group"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.3, delay: index * 0.02 }}
            whileHover={{ y: -2 }}
            onClick={() => onSelect(person)}
        >
            {/* Enrolled badge */}
            {person.enrolled && (
                <div className="absolute top-3 right-3">
                    <span className="badge badge-success">
                        <UserCheck size={9} fill="currentColor" /> Enrolled
                    </span>
                </div>
            )}

            {/* Avatar + Name */}
            <div className="flex items-center gap-3">
                <motion.div
                    layoutId={`avatar-${person.id}`}
                    className="w-10 h-10 rounded-lg flex items-center justify-center text-[13px] font-bold shrink-0"
                    style={{
                        background: "var(--bg-inner)",
                        color: person.enrolled
                            ? "#10b981"
                            : "var(--accent-violet, #8b5cf6)",
                    }}
                >
                    {person.representative_photo ? (
                        <img
                            src={getThumbnailUrl(person)}
                            alt=""
                            className="w-full h-full object-cover rounded-lg"
                        />
                    ) : (
                        initials
                    )}
                </motion.div>
                <div className="min-w-0">
                    <motion.p
                        layoutId={`name-${person.id}`}
                        className="text-[13px] font-semibold truncate"
                        style={{ color: "var(--text-primary)" }}
                    >
                        {displayName.replace(/_/g, " ")}
                    </motion.p>
                    {person.enrolled_name &&
                        person.enrolled_name !== person.name && (
                            <p
                                className="text-[10px] truncate"
                                style={{ color: "var(--text-muted)" }}
                            >
                                Cluster: {person.name}
                            </p>
                        )}
                </div>
            </div>

            {/* Stats */}
            <div
                className="flex items-center gap-4 mt-auto pt-2 "
            >
                <div
                    className="flex items-center gap-1.5 text-[11px]"
                    style={{ color: "var(--text-secondary)" }}
                >
                    <Camera size={12} fill="currentColor" strokeWidth={1.5} />
                    <span
                        className="font-semibold"
                        style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "10px",
                        }}
                    >
                        {person.solo_photos}
                    </span>
                    <span style={{ color: "var(--text-muted)" }}>solo</span>
                </div>
                <div
                    className="flex items-center gap-1.5 text-[11px]"
                    style={{ color: "var(--text-secondary)" }}
                >
                    <UsersRound size={12} fill="currentColor" strokeWidth={1.5} />
                    <span
                        className="font-semibold"
                        style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "10px",
                        }}
                    >
                        {person.group_photos}
                    </span>
                    <span style={{ color: "var(--text-muted)" }}>group</span>
                </div>
                <div
                    className="ml-auto text-[10px]"
                    style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                    }}
                >
                    {person.face_count} faces
                </div>
            </div>
        </motion.div>
    );
}

function PersonDetailsModal({
    person,
    onClose,
}: {
    person: PersonItem;
    onClose: () => void;
}) {
    const [cloudLoading, setCloudLoading] = useState(false);
    const displayName = person.enrolled_name ?? person.name;

    const initials = displayName
        .split(/[_\s]+/)
        .map((w) => w[0]?.toUpperCase())
        .slice(0, 2)
        .join("");

    const handleLocalClick = async (e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await openLocalPersonFolder(displayName);
            onClose();
        } catch (err) {
            console.error("Failed to open local folder", err);
        }
    };

    const handleCloudClick = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setCloudLoading(true);
        try {
            const res = await getPersonCloudUrl(displayName);
            if (res?.url) {
                window.open(res.url, "_blank");
            }
        } catch (err) {
            console.error("Failed to fetch cloud url", err);
        } finally {
            setCloudLoading(false);
            onClose();
        }
    };

    return (
        <motion.div
            layoutId={`card-${person.id}`}
            exit={{
                opacity: 0,
                scale: 0.9,
                y: 20,
                transition: { duration: 0.4, ease: "easeOut" }
            }}
            className="relative z-10 w-full max-w-sm rounded-[32px] p-6 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.2)] overflow-hidden border pointer-events-auto"
            style={{
                backgroundColor: "var(--bg-card)",
                borderColor: "var(--divider)",
                color: "var(--text-primary)"
            }}
            onClick={(e) => e.stopPropagation()}
        >
            <button
                className="absolute top-4 right-4 transition-colors p-2 rounded-full z-20"
                style={{
                    backgroundColor: "var(--bg-inner)",
                    color: "var(--text-muted)"
                }}
                onClick={onClose}
            >
                <X size={20} />
            </button>

            <div className="flex flex-col items-center gap-6">
                {/* Large Thumbnail */}
                <div className="relative group/thumb mt-4">
                    <motion.div
                        layoutId={`avatar-${person.id}`}
                        className="w-48 h-48 rounded-[24px] overflow-hidden border bg-zinc-800 shadow-2xl relative z-10"
                        style={{ borderColor: "var(--divider)" }}
                    >
                        {person.representative_photo ? (
                            <img
                                src={getThumbnailUrl(person)}
                                alt={displayName}
                                className="w-full h-full object-cover transition-transform duration-700 group-hover/thumb:scale-110"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-4xl font-bold text-zinc-600 bg-zinc-800">
                                {initials}
                            </div>
                        )}
                    </motion.div>
                    <div className="absolute inset-0 bg-accent-primary/20 blur-3xl rounded-full -z-0 opacity-50 group-hover/thumb:opacity-80 transition-opacity" />
                </div>

                <div className="text-center">
                    <motion.h2
                        layoutId={`name-${person.id}`}
                        className="text-2xl font-black tracking-tight leading-tight"
                        style={{ color: "var(--text-primary)" }}
                    >
                        {displayName.replace(/_/g, " ")}
                    </motion.h2>
                    {person.enrolled_name && person.enrolled_name !== person.name && (
                        <p className="text-xs mt-1 uppercase tracking-widest font-bold" style={{ color: "var(--text-muted)" }}>
                            Cluster: {person.name}
                        </p>
                    )}
                </div>

                <div className="w-full h-px my-2" style={{ backgroundColor: "var(--divider)" }} />

                <div className="w-full grid grid-cols-2 gap-4">
                    <motion.button
                        whileHover={{ scale: 1.02, filter: "brightness(1.05)" }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleLocalClick}
                        className="font-black py-4 rounded-2xl flex flex-col items-center justify-center gap-2 border shadow-xl transition-all h-28"
                        style={{
                            backgroundColor: "var(--bg-elevated)",
                            color: "var(--text-primary)",
                            borderColor: "var(--divider)"
                        }}
                    >
                        <FolderOpen size={24} style={{ color: "var(--text-secondary)" }} />
                        <span className="text-[11px] uppercase tracking-[0.2em]">Local disk</span>
                    </motion.button>

                    <motion.button
                        whileHover={{ scale: 1.02, filter: "brightness(1.1)" }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleCloudClick}
                        disabled={cloudLoading}
                        className="font-black py-4 rounded-2xl flex flex-col items-center justify-center gap-2 shadow-xl transition-all disabled:opacity-50 h-28"
                        style={{
                            backgroundColor: "#10b981",
                            color: "#ffffff"
                        }}
                    >
                        {cloudLoading ? <Loader2 size={24} className="animate-spin" /> : <Cloud size={24} />}
                        <span className="text-[11px] uppercase tracking-[0.2em]">
                            {cloudLoading ? "Loading..." : "Cloud drive"}
                        </span>
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
}
