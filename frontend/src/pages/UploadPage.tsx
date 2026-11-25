import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  Link2,
  Loader2,
  Sliders,
  Sparkles,
  UploadCloud,
  Youtube,
  AlertCircle,
} from "lucide-react";
import { api, formatDuration, uploadVideoWithProgress } from "../api/client";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { DropZoneUploader } from "../components/video/DropZoneUploader";
import type { AspectRatio, ExportQuality, YouTubePreview } from "../types";

export function UploadPage() {
  const navigate = useNavigate();
  const abortRef = useRef<AbortController | null>(null);

  const [sourceMode, setSourceMode] = useState<"file" | "youtube">("file");
  const [minDurationSec, setMinDurationSec] = useState(10);
  const [maxDurationSec, setMaxDurationSec] = useState(1200);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [detectedDuration, setDetectedDuration] = useState<number | null>(null);

  // YouTube link state
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [checkingYoutube, setCheckingYoutube] = useState(false);
  const [ytPreview, setYtPreview] = useState<YouTubePreview | null>(null);

  // Shared AI configuration
  const [title, setTitle] = useState("");
  const [targetShortsCount, setTargetShortsCount] = useState(10);
  const [defaultAspectRatio, setDefaultAspectRatio] = useState<AspectRatio>("9:16");
  const [defaultQuality, setDefaultQuality] = useState<ExportQuality>("1080p");

  const [submitting, setSubmitting] = useState(false);
  const [progressPercent, setProgressPercent] = useState(0);
  const [uploadSpeed, setUploadSpeed] = useState(0);
  const [uploadedBytes, setUploadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getHealth()
      .then((health) => {
        setMinDurationSec(health.min_video_duration_seconds);
        setMaxDurationSec(health.max_video_duration_seconds);
      })
      .catch(() => {});
  }, []);

  const handleFileSelected = (file: File | null, dur: number | null) => {
    setSelectedFile(file);
    setDetectedDuration(dur);
    setError(null);
    if (file && !title.trim()) {
      const base = file.name.replace(/\.[^.]+$/, "");
      setTitle(base);
    }
    if (!file && sourceMode === "file") {
      setTitle("");
    }
  };

  const handlePreviewYoutube = async () => {
    if (!youtubeUrl.trim()) {
      setError("Please paste a YouTube video link first.");
      return;
    }
    setError(null);
    setCheckingYoutube(true);
    setYtPreview(null);
    try {
      const preview = await api.previewYoutube(youtubeUrl.trim());
      setYtPreview(preview);
      if (!title.trim()) {
        setTitle(preview.title);
      }
      if (!preview.valid_duration && preview.validation_message) {
        setError(preview.validation_message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load YouTube video details.");
    } finally {
      setCheckingYoutube(false);
    }
  };

  const fileDurationInvalid =
    detectedDuration !== null &&
    (detectedDuration < minDurationSec || detectedDuration > maxDurationSec);

  const ytDurationInvalid = ytPreview !== null && !ytPreview.valid_duration;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (sourceMode === "file") {
      if (!selectedFile) {
        setError("Please select a video file first.");
        return;
      }
      if (fileDurationInvalid) {
        setError(
          `Selected video must be under ${Math.round(maxDurationSec / 60)} minutes (at least ${Math.round(minDurationSec)}s).`
        );
        return;
      }

      setSubmitting(true);
      setProgressPercent(0);
      setUploadedBytes(0);
      setTotalBytes(selectedFile.size);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const project = await uploadVideoWithProgress({
          file: selectedFile,
          title,
          targetShortsCount,
          defaultAspectRatio,
          defaultQuality,
          autoProcess: true,
          signal: controller.signal,
          onProgress: (info) => {
            setProgressPercent(info.percent);
            setUploadSpeed(info.speedBytesPerSec);
            setUploadedBytes(info.loaded);
            setTotalBytes(info.total);
          },
        });
        navigate(`/videos/${project.id}/processing`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setSubmitting(false);
        abortRef.current = null;
      }
      return;
    }

    // YouTube link mode
    if (!youtubeUrl.trim()) {
      setError("Please paste a YouTube video link.");
      return;
    }
    if (ytDurationInvalid) {
      setError(ytPreview?.validation_message || "YouTube video duration exceeds the 20-minute limit.");
      return;
    }

    setSubmitting(true);
    try {
      const project = await api.importYoutube({
        url: youtubeUrl.trim(),
        title,
        targetShortsCount,
        defaultAspectRatio,
        defaultQuality,
        autoProcess: true,
      });
      navigate(`/videos/${project.id}/processing`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import YouTube video.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Upload or Import Video</h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload a local file (MP4, MOV, MKV, WebM) or paste a YouTube link under {Math.round(maxDurationSec / 60)} minutes. Clipora AI will transcribe, detect scenes, and generate 5–15 engaging shorts.
        </p>
      </div>

      {/* Source Mode Switcher */}
      <div className="inline-flex rounded-2xl border border-white/10 bg-[#0d121f] p-1.5">
        <button
          type="button"
          disabled={submitting}
          onClick={() => {
            setSourceMode("file");
            setError(null);
          }}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-colors ${
            sourceMode === "file"
              ? "bg-violet-600 text-white shadow"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <UploadCloud className="h-4 w-4" />
          Upload Video File
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => {
            setSourceMode("youtube");
            setError(null);
          }}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold transition-colors ${
            sourceMode === "youtube"
              ? "bg-violet-600 text-white shadow"
              : "text-slate-400 hover:text-white"
          }`}
        >
          <Youtube className="h-4 w-4" />
          Paste YouTube Link
        </button>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {sourceMode === "file" ? (
            <DropZoneUploader
              minDurationSec={minDurationSec}
              maxDurationSec={maxDurationSec}
              selectedFile={selectedFile}
              onFileSelected={handleFileSelected}
              uploading={submitting}
              progressPercent={progressPercent}
              uploadSpeedBytesPerSec={uploadSpeed}
              uploadedBytes={uploadedBytes}
              totalBytes={totalBytes}
              onCancelUpload={() => abortRef.current?.abort()}
            />
          ) : (
            <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 sm:p-6 space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-white">YouTube Video URL</label>
                <p className="text-xs text-slate-400">
                  Paste any public YouTube video, Shorts, or recorded stream link under {Math.round(maxDurationSec / 60)} minutes.
                </p>
                <div className="flex flex-col gap-2.5 sm:flex-row">
                  <div className="relative flex-1">
                    <Link2 className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
                    <input
                      type="url"
                      disabled={submitting}
                      value={youtubeUrl}
                      onChange={(e) => {
                        setYoutubeUrl(e.target.value);
                        setYtPreview(null);
                        setError(null);
                      }}
                      placeholder="https://www.youtube.com/watch?v=..."
                      className="w-full rounded-xl border border-white/10 bg-[#121829] py-2.5 pl-10 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
                    />
                  </div>
                  <button
                    type="button"
                    disabled={checkingYoutube || submitting || !youtubeUrl.trim()}
                    onClick={handlePreviewYoutube}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-40"
                  >
                    {checkingYoutube ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Checking…
                      </>
                    ) : (
                      "Check Link"
                    )}
                  </button>
                </div>
              </div>

              {ytPreview && (
                <div className="rounded-xl border border-white/10 bg-[#121829] p-4 space-y-3">
                  <div className="flex flex-col gap-4 sm:flex-row">
                    {ytPreview.thumbnail_url && (
                      <img
                        src={ytPreview.thumbnail_url}
                        alt={ytPreview.title}
                        className="h-28 w-48 shrink-0 rounded-lg border border-white/10 bg-black object-cover"
                      />
                    )}
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <h3 className="line-clamp-2 text-sm font-semibold text-white">{ytPreview.title}</h3>
                      <p className="text-xs text-slate-400">Channel: {ytPreview.channel}</p>
                      <p className="font-mono text-xs text-slate-300">
                        Duration: {formatDuration(ytPreview.duration)}
                      </p>
                    </div>
                  </div>

                  {ytPreview.valid_duration ? (
                    <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                      <span>YouTube video verified ({formatDuration(ytPreview.duration)}). Ready to import and analyze.</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-lg border border-rose-500/35 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                      <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                      <span>{ytPreview.validation_message}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 space-y-5 h-fit">
          <div className="flex items-center gap-2 border-b border-white/10 pb-3">
            <Sliders className="h-4 w-4 text-violet-400" />
            <h2 className="text-sm font-semibold text-white">AI Generation Settings</h2>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Project Title</label>
            <input
              type="text"
              value={title}
              disabled={submitting}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Tech Founder Interview Episode 14"
              className="w-full rounded-xl border border-white/10 bg-[#121829] px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <label className="font-medium text-slate-300">Target Shorts Count</label>
              <span className="font-mono font-semibold text-violet-300">{targetShortsCount} shorts</span>
            </div>
            <input
              type="range"
              min={5}
              max={15}
              step={1}
              disabled={submitting}
              value={targetShortsCount}
              onChange={(e) => setTargetShortsCount(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-[11px] text-slate-500">
              <span>5 min</span>
              <span>10–20s each</span>
              <span>15 max</span>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Default Aspect Ratio</label>
            <div className="grid grid-cols-3 gap-2">
              {(["9:16", "16:9", "1:1"] as AspectRatio[]).map((ar) => (
                <button
                  key={ar}
                  type="button"
                  disabled={submitting}
                  onClick={() => setDefaultAspectRatio(ar)}
                  className={`rounded-xl border py-2 text-xs font-semibold transition-colors ${
                    defaultAspectRatio === ar
                      ? "border-violet-500 bg-violet-500/20 text-white"
                      : "border-white/10 bg-[#121829] text-slate-400 hover:text-white"
                  }`}
                >
                  {ar}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300">Initial Render Quality</label>
            <div className="grid grid-cols-2 gap-2">
              {(["720p", "1080p"] as ExportQuality[]).map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={submitting}
                  onClick={() => setDefaultQuality(q)}
                  className={`rounded-xl border py-2 text-xs font-semibold transition-colors ${
                    defaultQuality === q
                      ? "border-cyan-500 bg-cyan-500/20 text-white"
                      : "border-white/10 bg-[#121829] text-slate-400 hover:text-white"
                  }`}
                >
                  {q} HD
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={
              submitting ||
              (sourceMode === "file"
                ? !selectedFile || fileDurationInvalid
                : !youtubeUrl.trim() || ytDurationInvalid)
            }
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-600/25 hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Sparkles className="h-4 w-4" />
            {submitting
              ? sourceMode === "file"
                ? `Uploading (${progressPercent}%)…`
                : "Starting YouTube Import…"
              : sourceMode === "file"
              ? "Upload & Start AI Analysis"
              : "Import YouTube & Start AI Analysis"}
          </button>
        </div>
      </form>
    </div>
  );
}
