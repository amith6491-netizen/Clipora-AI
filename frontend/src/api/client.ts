import type {
  AspectRatio,
  AuthResponse,
  Clip,
  ClipUpdatePayload,
  ExportQuality,
  ExportRecord,
  MomentCategory,
  ProgressEventPayload,
  SubtitlePreset,
  SubtitleStyle,
  SystemHealth,
  TranscriptPayload,
  User,
  VideoProject,
  YouTubePreview,
} from "../types";

const AUTH_STORAGE_KEY = "clipora_auth_token";

export function getAuthToken(): string | null {
  try {
    return window.localStorage.getItem(AUTH_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(AUTH_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  } catch {
    // ignore storage errors
  }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(init?.headers);
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("; ");
      }
    } catch {
      // keep default detail
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export interface UploadProgressInfo {
  loaded: number;
  total: number;
  percent: number;
  speedBytesPerSec: number;
}

export interface UploadVideoOptions {
  file: File;
  title?: string;
  targetShortsCount?: number;
  defaultAspectRatio?: AspectRatio;
  defaultQuality?: ExportQuality;
  autoProcess?: boolean;
  onProgress?: (info: UploadProgressInfo) => void;
  signal?: AbortSignal;
}

export function uploadVideoWithProgress(opts: UploadVideoOptions): Promise<VideoProject> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", opts.file);
    if (opts.title?.trim()) form.append("title", opts.title.trim());
    form.append("target_shorts_count", String(opts.targetShortsCount ?? 10));
    form.append("default_aspect_ratio", opts.defaultAspectRatio ?? "9:16");
    form.append("default_quality", opts.defaultQuality ?? "1080p");
    form.append("auto_process", String(opts.autoProcess ?? true));

    const startedAt = Date.now();

    xhr.upload.addEventListener("progress", (ev) => {
      if (!ev.lengthComputable || !opts.onProgress) return;
      const elapsedSec = Math.max(0.1, (Date.now() - startedAt) / 1000);
      opts.onProgress({
        loaded: ev.loaded,
        total: ev.total,
        percent: Math.min(100, Math.round((ev.loaded / ev.total) * 100)),
        speedBytesPerSec: ev.loaded / elapsedSec,
      });
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as VideoProject);
        } catch {
          reject(new ApiError("Invalid server response after upload.", xhr.status));
        }
      } else {
        let msg = `Upload failed (${xhr.status})`;
        try {
          const parsed = JSON.parse(xhr.responseText);
          if (parsed?.detail) msg = String(parsed.detail);
        } catch {
          // ignore
        }
        reject(new ApiError(msg, xhr.status));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new ApiError("Network error while uploading video. Please verify the backend is running.", 0));
    });

    xhr.addEventListener("abort", () => {
      reject(new ApiError("Upload cancelled by user.", 0));
    });

    if (opts.signal) {
      if (opts.signal.aborted) {
        xhr.abort();
        return;
      }
      opts.signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.open("POST", "/api/videos/upload");
    const token = getAuthToken();
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.send(form);
  });
}

export interface YouTubeImportOptions {
  url: string;
  title?: string;
  targetShortsCount?: number;
  defaultAspectRatio?: AspectRatio;
  defaultQuality?: ExportQuality;
  autoProcess?: boolean;
}

export const api = {
  getHealth: () => requestJson<SystemHealth>("/api/health"),

  register: (name: string, email: string, password: string) =>
    requestJson<AuthResponse>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    }),
  login: (email: string, password: string) =>
    requestJson<AuthResponse>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  me: () => requestJson<User>("/api/auth/me"),

  previewYoutube: (url: string) =>
    requestJson<YouTubePreview>("/api/videos/youtube/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),
  importYoutube: (opts: YouTubeImportOptions) =>
    requestJson<VideoProject>("/api/videos/youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: opts.url,
        title: opts.title?.trim() || undefined,
        target_shorts_count: opts.targetShortsCount ?? 10,
        default_aspect_ratio: opts.defaultAspectRatio ?? "9:16",
        default_quality: opts.defaultQuality ?? "1080p",
        auto_process: opts.autoProcess ?? true,
      }),
    }),

  listVideos: () => requestJson<VideoProject[]>("/api/videos"),
  getVideo: (videoId: string) => requestJson<VideoProject>(`/api/videos/${videoId}`),
  startProcessing: (videoId: string) =>
    requestJson<VideoProject>(`/api/videos/${videoId}/process`, { method: "POST" }),
  cancelProcessing: (videoId: string) =>
    requestJson<VideoProject>(`/api/videos/${videoId}/cancel`, { method: "POST" }),
  deleteVideo: (videoId: string) =>
    requestJson<void>(`/api/videos/${videoId}`, { method: "DELETE" }),
  getTranscript: (videoId: string) =>
    requestJson<TranscriptPayload>(`/api/videos/${videoId}/transcript`),

  listClips: (videoId: string, category?: MomentCategory | "all", sortBy: "score" | "timeline" | "duration" = "score") => {
    const params = new URLSearchParams({ sort_by: sortBy });
    if (category && category !== "all") params.set("category", category);
    return requestJson<Clip[]>(`/api/videos/${videoId}/clips?${params.toString()}`);
  },
  getClip: (clipId: string) => requestJson<Clip>(`/api/clips/${clipId}`),
  updateClip: (clipId: string, payload: ClipUpdatePayload) =>
    requestJson<Clip>(`/api/clips/${clipId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  regenerateAutoCaptions: (clipId: string) =>
    requestJson<Clip>(`/api/clips/${clipId}/auto-captions`, { method: "POST" }),
  renderClip: (clipId: string, quality: ExportQuality, aspectRatio?: AspectRatio) =>
    requestJson<Clip>(`/api/clips/${clipId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quality, aspect_ratio: aspectRatio }),
    }),

  listExports: (videoId?: string) =>
    requestJson<ExportRecord[]>(videoId ? `/api/videos/${videoId}/exports` : "/api/exports"),
  exportZip: (videoId: string, quality: ExportQuality, clipIds?: string[]) =>
    requestJson<ExportRecord>(`/api/videos/${videoId}/export-zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quality, clip_ids: clipIds }),
    }),
  getClipDownloadUrl: (clipId: string, quality: ExportQuality, aspectRatio?: AspectRatio) => {
    const params = new URLSearchParams({ quality });
    if (aspectRatio) params.set("aspect_ratio", aspectRatio);
    return `/api/clips/${clipId}/download?${params.toString()}`;
  },
};

export function subscribeToProgress(
  videoId: string,
  onEvent: (payload: ProgressEventPayload) => void,
  onError?: () => void
): () => void {
  const es = new EventSource(`/api/videos/${videoId}/progress`);
  es.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(ev.data) as ProgressEventPayload;
      onEvent(parsed);
      if (parsed.status === "completed" || parsed.status === "failed" || parsed.status === "cancelled") {
        es.close();
      }
    } catch {
      // ignore malformed heartbeat
    }
  };
  es.onerror = () => {
    es.close();
    onError?.();
  };
  return () => es.close();
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

export function formatTimestampPrecise(seconds: number): string {
  const safe = Math.max(0, seconds);
  const mins = Math.floor(safe / 60);
  const rem = (safe % 60).toFixed(1).padStart(4, "0");
  return `${mins}:${rem}`;
}

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const idx = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / Math.pow(1024, idx)).toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export const CATEGORY_META: Record<
  MomentCategory,
  { label: string; colorClass: string; bgClass: string; borderClass: string }
> = {
  interesting: {
    label: "Interesting",
    colorClass: "text-cyan-300",
    bgClass: "bg-cyan-500/15",
    borderClass: "border-cyan-500/30",
  },
  funny: {
    label: "Funny",
    colorClass: "text-amber-300",
    bgClass: "bg-amber-500/15",
    borderClass: "border-amber-500/30",
  },
  important: {
    label: "Important",
    colorClass: "text-rose-300",
    bgClass: "bg-rose-500/15",
    borderClass: "border-rose-500/30",
  },
  motivational: {
    label: "Motivational",
    colorClass: "text-emerald-300",
    bgClass: "bg-emerald-500/15",
    borderClass: "border-emerald-500/30",
  },
  educational: {
    label: "Educational",
    colorClass: "text-indigo-300",
    bgClass: "bg-indigo-500/15",
    borderClass: "border-indigo-500/30",
  },
  engaging: {
    label: "Engaging",
    colorClass: "text-violet-300",
    bgClass: "bg-violet-500/15",
    borderClass: "border-violet-500/30",
  },
};

export const SUBTITLE_PRESETS: Record<
  SubtitlePreset,
  { label: string; description: string; defaults: Partial<SubtitleStyle> }
> = {
  bold_pop: {
    label: "Bold Pop",
    description: "High-contrast social hook style with punchy background box",
    defaults: {
      preset: "bold_pop",
      text_color: "#FFFFFF",
      accent_color: "#A855F7",
      background_color: "#0B0F19",
      background_opacity: 0.78,
      outline_color: "#000000",
      font_size: 36,
      uppercase: true,
    },
  },
  neon_box: {
    label: "Neon Pill",
    description: "Vibrant studio badge behind bold kinetic captions",
    defaults: {
      preset: "neon_box",
      text_color: "#FFFFFF",
      accent_color: "#22D3EE",
      background_color: "#5B21B6",
      background_opacity: 0.85,
      outline_color: "#090D16",
      font_size: 34,
      uppercase: false,
    },
  },
  minimal_clean: {
    label: "Minimal Clean",
    description: "Subtle editorial captions with crisp dark outline",
    defaults: {
      preset: "minimal_clean",
      text_color: "#F8FAFC",
      accent_color: "#38BDF8",
      background_color: "#000000",
      background_opacity: 0.0,
      outline_color: "#0F172A",
      font_size: 30,
      uppercase: false,
    },
  },
  classic_cinema: {
    label: "Classic Cinema",
    description: "Warm broadcast subtitle look with strong drop shadow",
    defaults: {
      preset: "classic_cinema",
      text_color: "#FEF08A",
      accent_color: "#FBBF24",
      background_color: "#000000",
      background_opacity: 0.45,
      outline_color: "#111827",
      font_size: 32,
      uppercase: false,
    },
  },
};
