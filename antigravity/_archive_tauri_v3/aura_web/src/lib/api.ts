// ============================================================
// AURA — API Client
// Typed fetch wrappers for the FastAPI backend at localhost:8000
// ============================================================

export const isProd = process.env.NODE_ENV === "production";
export const API_BASE = isProd ? "http://localhost:8000/api" : "/api";
export const WS_BASE = isProd ? "ws://localhost:8000/api/admin" : "/api/admin";

// ---- Types ----

export interface StatsResponse {
    total_photos: number;
    total_faces: number;
    total_persons: number;
    total_enrolled: number;
    photos_by_status: Record<string, number>;
}

export interface PersonItem {
    id: number;
    name: string;
    face_count: number;
    solo_photos: number;
    group_photos: number;
    enrolled: boolean;
    enrolled_name: string | null;
    enrolled_at: string | null;
    representative_photo: string | null;
    face_bbox?: { x: number; y: number; w: number; h: number } | null;
}

export interface HealthResponse {
    status: string;
    service: string;
}

export interface GPUInfo {
    gpu_found: boolean;
    gpu_name: string;
    gpu_architecture: string;
    compute_capability: number;
    vram_mb: number;
    driver_version: string;
    cuda_installed: boolean;
    cuda_version: string;
    cudnn_installed: boolean;
    cudnn_version: string;
    ort_gpu_installed: boolean;
    cuda_provider_available: boolean;
    available_providers: string[];
    wizard_step: number;
    status_message: string;
    can_proceed: boolean;
}

export interface StuckPhoto {
    id: number;
    path: string;
    status: string;
    created_at: string;
}

export interface WhatsAppStatus {
    total_enrolled: number;
    sendable: number;
    session_exists: boolean;
    is_running: boolean;
}

export interface WorkerStatus {
    is_running: boolean;
}

export interface AuthStatusResponse {
    token_exists: boolean;
    token_valid: boolean;
    token_expired: boolean;
    has_refresh: boolean;
    expiry_str: string;
}

export interface ProcessStatus {
    stats: StatsResponse;
    progress: Record<string, number | string>;
    upload: Record<string, number>;
}

// ---- Fetch helpers ----

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });

    if (!res.ok) {
        throw new Error(`API error ${res.status}: ${res.statusText}`);
    }

    return res.json() as Promise<T>;
}

// ---- Public API ----

export async function fetchStats(): Promise<StatsResponse> {
    return apiFetch<StatsResponse>("/stats");
}

export async function fetchPersons(): Promise<PersonItem[]> {
    return apiFetch<PersonItem[]>("/persons");
}

export async function openLocalPersonFolder(name: string): Promise<{ status: string }> {
    return apiFetch(`/admin/person/open-local?name=${encodeURIComponent(name)}`, {
        method: "GET"
    });
}

export async function getPersonCloudUrl(name: string): Promise<{ url: string | null }> {
    return apiFetch(`/admin/person/cloud-url?name=${encodeURIComponent(name)}`, {
        method: "GET"
    });
}

export async function fetchHealth(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/health");
}

// ---- Admin API ----

export async function fetchSettings(): Promise<Record<string, string>> {
    return apiFetch<Record<string, string>>("/admin/settings");
}

export async function updateSettings(settings: Record<string, string | number | boolean>): Promise<{ status: string; updated: string[] }> {
    return apiFetch("/admin/settings", {
        method: "PUT",
        body: JSON.stringify(settings),
    });
}

export async function mergePersons(keepId: number, removeId: number) {
    return apiFetch("/admin/merge", {
        method: "POST",
        body: JSON.stringify({ person_id_keep: keepId, person_id_remove: removeId }),
    });
}

export async function runSelfHeal() {
    return apiFetch<{ status: string; results: Record<string, unknown> }>("/admin/self-heal", {
        method: "POST",
    });
}

export async function fetchGPUStatus(): Promise<GPUInfo> {
    return apiFetch<GPUInfo>("/admin/gpu");
}

export async function updateGPU(gpuOn: boolean, deviceId: number = 0) {
    return apiFetch("/admin/gpu", {
        method: "PUT",
        body: JSON.stringify({ gpu_on: gpuOn, device_id: deviceId }),
    });
}

export async function fetchStuckPhotos(): Promise<StuckPhoto[]> {
    return apiFetch<StuckPhoto[]>("/admin/stuck-photos");
}

export async function fixStuckPhotos(action: "reset" | "skip", photoIds: number[] = []) {
    return apiFetch("/admin/stuck-photos", {
        method: "POST",
        body: JSON.stringify({ action, photo_ids: photoIds }),
    });
}

export async function fetchWhatsAppStatus(): Promise<WhatsAppStatus> {
    return apiFetch<WhatsAppStatus>("/admin/whatsapp/status");
}

export async function startWhatsApp(): Promise<{ status: string; message: string }> {
    return apiFetch("/admin/whatsapp/start", {
        method: "POST",
    });
}

export async function stopWhatsApp(): Promise<{ status: string; message: string }> {
    return apiFetch("/admin/whatsapp/stop", {
        method: "POST",
    });
}

export async function fetchAuthStatus(): Promise<AuthStatusResponse> {
    return apiFetch<AuthStatusResponse>("/admin/auth/status");
}

export async function triggerReauth(): Promise<{ status: string; message: string }> {
    return apiFetch("/admin/auth/reauth", {
        method: "POST",
    });
}

export async function fetchWorkerStatus(): Promise<WorkerStatus> {
    return apiFetch<WorkerStatus>("/admin/worker/status");
}

export async function startWorker(): Promise<{ status: string; message: string }> {
    return apiFetch("/admin/worker/start", {
        method: "POST",
    });
}

export async function stopWorker(): Promise<{ status: string; message: string }> {
    return apiFetch("/admin/worker/stop", {
        method: "POST",
    });
}
