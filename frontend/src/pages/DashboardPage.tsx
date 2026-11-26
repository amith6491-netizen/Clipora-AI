import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  Clock,
  Film,
  FolderOpen,
  Instagram,
  Plus,
  Sparkles,
  StopCircle,
  Trash2,
  UploadCloud,
  Youtube,
} from "lucide-react";
import { api, formatBytes, formatDuration, resolveApiUrl } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { VideoStatusBadge } from "../components/layout/StatusBadge";
import type { VideoProject } from "../types";

function ProjectThumb({ src, title }: { src: string; title: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) {
    return (
      <div className="flex h-24 w-36 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-[#121829] text-slate-500">
        <Film className="h-6 w-6" />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={title}
      onError={() => setBroken(true)}
      className="h-24 w-36 shrink-0 rounded-xl border border-white/10 bg-black object-cover"
    />
  );
}

export function DashboardPage() {
  const [videos, setVideos] = useState<VideoProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const loadVideos = async () => {
    try {
      const list = await api.listVideos();
      setVideos(list);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load video projects.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVideos();
    const timer = window.setInterval(loadVideos, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const handleDelete = async (videoId: string, title: string) => {
    if (!window.confirm(`Delete "${title}" and all its generated shorts?`)) return;
    setDeletingId(videoId);
    try {
      await api.deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete video.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleCancel = async (videoId: string) => {
    setCancellingId(videoId);
    try {
      const updated = await api.cancelProcessing(videoId);
      setVideos((prev) => prev.map((v) => (v.id === videoId ? updated : v)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel processing.");
    } finally {
      setCancellingId(null);
    }
  };

  const totalClips = videos.reduce((acc, v) => acc + v.clips_count, 0);
  const readyCount = videos.filter((v) => v.status === "completed").length;
  const activeCount = videos.filter((v) => v.status === "processing" || v.status === "queued").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Studio Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Manage uploaded videos (up to 20 minutes), monitor AI analysis, and open generated shorts.
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/20 hover:opacity-95"
        >
          <Plus className="h-4 w-4" />
          Upload New Video
        </Link>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Total Projects</span>
            <Film className="h-4 w-4 text-violet-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{videos.length}</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>AI Shorts Generated</span>
            <Sparkles className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{totalClips}</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Completed Videos</span>
            <FolderOpen className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{readyCount}</div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Active AI Jobs</span>
            <Activity className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{activeCount}</div>
        </div>
      </div>

      {/* Video List */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((k) => (
            <div key={k} className="h-44 animate-pulse rounded-2xl border border-white/10 bg-[#0d121f]" />
          ))}
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={<UploadCloud className="h-6 w-6" />}
          title="No video projects yet"
          description="Upload an MP4, MOV, MKV, or WebM video (up to 20 minutes) to start generating AI-scored short clips."
          action={
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-500"
            >
              <UploadCloud className="h-4 w-4" />
              Upload First Video
            </Link>
          }
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {videos.map((video) => (
            <div
              key={video.id}
              className="flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0d121f] p-4 sm:p-5 transition-colors hover:border-white/20"
            >
              <div className="flex gap-4">
                <ProjectThumb src={resolveApiUrl(video.poster_url)} title={video.title} />
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="truncate text-base font-semibold text-white">{video.title}</h3>
                    <VideoStatusBadge status={video.status} />
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {formatDuration(video.duration)}
                    </span>
                    <span>
                      {video.width}×{video.height}
                    </span>
                    {video.size_bytes > 0 && <span>{formatBytes(video.size_bytes)}</span>}
                    {video.source_type === "youtube" ? (
                      <span className="inline-flex items-center gap-1 text-rose-300">
                        <Youtube className="h-3.5 w-3.5" />
                        YouTube
                      </span>
                    ) : video.source_type === "instagram" ? (
                      <span className="inline-flex items-center gap-1 text-fuchsia-300">
                        <Instagram className="h-3.5 w-3.5" />
                        Instagram
                      </span>
                    ) : (
                      <span className="uppercase">{video.format_ext.replace(".", "")}</span>
                    )}
                  </div>

                  {video.status === "processing" || video.status === "queued" ? (
                    <div className="space-y-1 pt-1">
                      <div className="flex justify-between text-[11px] text-violet-300">
                        <span>Stage: {video.current_stage.replace("_", " ")}</span>
                        <span className="font-mono">{video.progress.toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all"
                          style={{ width: `${video.progress}%` }}
                        />
                      </div>
                    </div>
                  ) : video.status === "failed" ? (
                    <p className="line-clamp-2 text-xs text-rose-300">{video.error_message || "Processing failed."}</p>
                  ) : video.status === "cancelled" ? (
                    <p className="text-xs text-slate-400">Processing cancelled by user.</p>
                  ) : video.source_type === "instagram" ? (
                    <p className="text-xs text-slate-400">
                      <span className="font-semibold text-slate-200">{video.clips_count}</span> editable HD video ready in Studio
                    </p>
                  ) : (
                    <p className="text-xs text-slate-400">
                      <span className="font-semibold text-slate-200">{video.clips_count}</span> shorts •{" "}
                      {video.analysis_summary.scene_count} scenes • {video.analysis_summary.word_count} words
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={`/videos/${video.id}/processing`}
                    className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
                  >
                    Pipeline Status
                  </Link>
                  {(video.status === "processing" || video.status === "queued") && (
                    <button
                      type="button"
                      disabled={cancellingId === video.id}
                      onClick={() => handleCancel(video.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-rose-500/35 bg-rose-500/15 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/25 disabled:opacity-50"
                    >
                      <StopCircle className="h-3.5 w-3.5" />
                      {cancellingId === video.id ? "Cancelling…" : "Cancel"}
                    </button>
                  )}
                  {video.clips_count > 0 && (
                    <>
                      <Link
                        to={`/videos/${video.id}/shorts`}
                        className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-500"
                      >
                        View Shorts ({video.clips_count})
                      </Link>
                      <Link
                        to={`/downloads?video=${video.id}`}
                        className="rounded-lg border border-cyan-500/35 bg-cyan-500/15 px-3 py-1.5 text-xs font-medium text-cyan-200 hover:bg-cyan-500/25"
                      >
                        Export / ZIP
                      </Link>
                    </>
                  )}
                </div>

                <button
                  type="button"
                  disabled={deletingId === video.id}
                  onClick={() => handleDelete(video.id, video.title)}
                  className="inline-flex items-center gap-1 rounded-lg p-1.5 text-xs text-slate-400 hover:bg-rose-500/15 hover:text-rose-300 disabled:opacity-50"
                  aria-label="Delete video project"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
