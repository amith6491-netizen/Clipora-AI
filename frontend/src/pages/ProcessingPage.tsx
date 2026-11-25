import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Cpu,
  Loader2,
  RefreshCw,
  Sparkles,
  StopCircle,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { api, formatDuration, subscribeToProgress } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { VideoStatusBadge } from "../components/layout/StatusBadge";
import type { PipelineStep, VideoProject } from "../types";

export function ProcessingPage() {
  const { videoId: routeVideoId } = useParams<{ videoId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [activeVideoId, setActiveVideoId] = useState<string>(
    routeVideoId || searchParams.get("video") || ""
  );
  const [video, setVideo] = useState<VideoProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (routeVideoId) {
      setActiveVideoId(routeVideoId);
      return;
    }
    const qVid = searchParams.get("video");
    if (qVid) {
      setActiveVideoId(qVid);
    }
  }, [routeVideoId, searchParams]);

  useEffect(() => {
    api
      .listVideos()
      .then((list) => {
        setProjects(list);
        if (!routeVideoId && !searchParams.get("video") && list.length > 0) {
          const preferred =
            list.find((v) => v.status === "processing" || v.status === "queued") || list[0];
          setActiveVideoId(preferred.id);
        } else if (list.length === 0 && !routeVideoId) {
          setLoading(false);
        }
      })
      .catch(() => {
        if (!routeVideoId) setLoading(false);
      });
  }, [routeVideoId]);

  useEffect(() => {
    if (!activeVideoId) return;
    let active = true;
    let unsub: (() => void) | null = null;
    let pollTimer: number | null = null;
    setLoading(true);

    const fetchProject = async () => {
      try {
        const doc = await api.getVideo(activeVideoId);
        if (!active) return null;
        setVideo(doc);
        setLoading(false);
        return doc;
      } catch (err) {
        if (!active) return null;
        setError(err instanceof Error ? err.message : "Failed to load video processing status.");
        setLoading(false);
        return null;
      }
    };

    fetchProject().then((doc) => {
      if (!active || !doc) return;
      if (doc.status === "completed" || doc.status === "failed" || doc.status === "cancelled") return;

      unsub = subscribeToProgress(
        activeVideoId,
        (ev) => {
          if (!active) return;
          setVideo((prev) =>
            prev
              ? {
                  ...prev,
                  status: ev.status,
                  progress: ev.progress,
                  current_stage: ev.current_stage,
                  pipeline_steps: ev.pipeline_steps,
                  error_message: ev.error_message ?? prev.error_message,
                }
              : prev
          );
          if (ev.status === "completed" || ev.status === "failed" || ev.status === "cancelled") {
            fetchProject();
          }
        },
        () => {
          if (pollTimer === null && active) {
            pollTimer = window.setInterval(async () => {
              const latest = await fetchProject();
              if (
                latest &&
                (latest.status === "completed" ||
                  latest.status === "failed" ||
                  latest.status === "cancelled")
              ) {
                if (pollTimer !== null) window.clearInterval(pollTimer);
              }
            }, 2500);
          }
        }
      );
    });

    return () => {
      active = false;
      unsub?.();
      if (pollTimer !== null) window.clearInterval(pollTimer);
    };
  }, [activeVideoId]);

  const handleSelectProject = (newId: string) => {
    setActiveVideoId(newId);
    if (routeVideoId) {
      navigate(`/videos/${newId}/processing`);
    } else {
      setSearchParams({ video: newId });
    }
  };

  const handleRetry = async () => {
    if (!activeVideoId) return;
    setRetrying(true);
    setError(null);
    try {
      const updated = await api.startProcessing(activeVideoId);
      setVideo(updated);
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restart pipeline.");
    } finally {
      setRetrying(false);
    }
  };

  const handleCancel = async () => {
    if (!activeVideoId) return;
    setCancelling(true);
    setError(null);
    try {
      const updated = await api.cancelProcessing(activeVideoId);
      setVideo(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel processing.");
    } finally {
      setCancelling(false);
    }
  };

  const renderStepIcon = (step: PipelineStep) => {
    if (step.status === "completed") return <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
    if (step.status === "running") return <Loader2 className="h-5 w-5 animate-spin text-violet-400" />;
    if (step.status === "failed") return <XCircle className="h-5 w-5 text-rose-400" />;
    if (step.status === "cancelled") return <StopCircle className="h-5 w-5 text-amber-400" />;
    return <Circle className="h-5 w-5 text-slate-600" />;
  };

  if (loading) {
    return <div className="h-64 animate-pulse rounded-2xl border border-white/10 bg-[#0d121f]" />;
  }

  if (!activeVideoId || !video) {
    if (error) return <ErrorBanner message={error} />;
    return (
      <EmptyState
        icon={<Cpu className="h-6 w-6" />}
        title="No AI analysis jobs yet"
        description="Upload a video file or paste a YouTube link to watch the real-time AI analysis pipeline."
        action={
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-500"
          >
            <UploadCloud className="h-4 w-4" />
            Upload or Import Video
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{video.title}</h1>
            <VideoStatusBadge status={video.status} />
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Source duration: {formatDuration(video.duration)} • {video.width}×{video.height} • Target {video.target_shorts_count} shorts
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {projects.length > 1 && (
            <select
              value={activeVideoId}
              onChange={(e) => handleSelectProject(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#121829] px-3 py-2 text-xs text-white"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.status})
                </option>
              ))}
            </select>
          )}

          {(video.status === "processing" || video.status === "queued") && (
            <button
              type="button"
              disabled={cancelling}
              onClick={handleCancel}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-500/45 bg-rose-500/15 px-4 py-2 text-sm font-semibold text-rose-200 hover:bg-rose-500/25 disabled:opacity-50"
            >
              <StopCircle className="h-4 w-4" />
              {cancelling ? "Cancelling…" : "Cancel Processing"}
            </button>
          )}
          {(video.status === "failed" || video.status === "uploaded" || video.status === "cancelled") && (
            <button
              type="button"
              disabled={retrying}
              onClick={handleRetry}
              className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/15 px-4 py-2 text-sm font-medium text-amber-200 hover:bg-amber-500/25"
            >
              <RefreshCw className={`h-4 w-4 ${retrying ? "animate-spin" : ""}`} />
              {video.status === "failed"
                ? "Retry AI Analysis"
                : video.status === "cancelled"
                ? "Restart AI Analysis"
                : "Start AI Analysis"}
            </button>
          )}
          {video.status === "completed" && (
            <Link
              to={`/videos/${video.id}/shorts`}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/25"
            >
              <Sparkles className="h-4 w-4" />
              Open Shorts Gallery ({video.clips_count})
              <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
      </div>

      <ErrorBanner message={error || video.error_message} />

      {/* Overall Progress Card */}
      <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold text-white">Overall AI Pipeline Progress</span>
          <span className="font-mono font-bold text-violet-300">{video.progress.toFixed(1)}%</span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              video.status === "failed"
                ? "bg-rose-500"
                : video.status === "cancelled"
                ? "bg-slate-500"
                : video.status === "completed"
                ? "bg-emerald-500"
                : "bg-gradient-to-r from-violet-500 via-fuchsia-500 to-cyan-400"
            }`}
            style={{ width: `${video.progress}%` }}
          />
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="grid gap-3">
        {video.pipeline_steps.map((step, idx) => (
          <div
            key={step.key}
            className={`rounded-2xl border p-4 transition-colors ${
              step.status === "running"
                ? "border-violet-500/45 bg-violet-500/10"
                : step.status === "completed"
                ? "border-emerald-500/25 bg-[#0d121f]"
                : step.status === "failed"
                ? "border-rose-500/40 bg-rose-500/10"
                : step.status === "cancelled"
                ? "border-amber-500/35 bg-amber-500/10"
                : "border-white/10 bg-[#0b0f19]"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                {renderStepIcon(step)}
                <div>
                  <div className="text-sm font-semibold text-white">
                    {idx + 1}. {step.label}
                  </div>
                  <div className="text-xs text-slate-400">{step.detail || "Pending"}</div>
                </div>
              </div>
              <span className="font-mono text-xs text-slate-300">{step.progress.toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>

      {/* Telemetry Summary once completed */}
      {video.status === "completed" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { label: "Language", val: video.analysis_summary.language.toUpperCase() },
            { label: "Words Transcribed", val: video.analysis_summary.word_count },
            { label: "Scenes Detected", val: video.analysis_summary.scene_count },
            { label: "Audio Peaks", val: video.analysis_summary.peak_audio_moments },
            { label: "Windows Ranked", val: video.analysis_summary.candidate_windows_evaluated },
          ].map((stat) => (
            <div key={stat.label} className="rounded-xl border border-white/10 bg-[#0d121f] p-4">
              <div className="text-xs text-slate-400">{stat.label}</div>
              <div className="mt-1 text-xl font-bold text-white">{stat.val}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
