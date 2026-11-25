import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Archive, CheckCircle2, Download, Film, Loader2 } from "lucide-react";
import { api, formatBytes } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBanner } from "../components/common/ErrorBanner";
import type { Clip, ExportQuality, ExportRecord, VideoProject } from "../types";

export function DownloadManagerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedVideoId = searchParams.get("video") || "";

  const [videos, setVideos] = useState<VideoProject[]>([]);
  const [clips, setClips] = useState<Clip[]>([]);
  const [exportsList, setExportsList] = useState<ExportRecord[]>([]);
  const [quality, setQuality] = useState<ExportQuality>("1080p");
  const [buildingZip, setBuildingZip] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .listVideos()
      .then((list) => {
        const completed = list.filter((v) => v.clips_count > 0);
        setVideos(completed);
        if (!selectedVideoId && completed.length > 0) {
          setSearchParams({ video: completed[0].id }, { replace: true });
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load projects."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedVideoId) {
      setClips([]);
      setExportsList([]);
      return;
    }
    Promise.all([api.listClips(selectedVideoId), api.listExports(selectedVideoId)])
      .then(([c, ex]) => {
        setClips(c);
        setExportsList(ex);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load project exports."));
  }, [selectedVideoId]);

  const handleExportZip = async () => {
    if (!selectedVideoId) return;
    setBuildingZip(true);
    setError(null);
    try {
      const record = await api.exportZip(selectedVideoId, quality);
      setExportsList((prev) => [record, ...prev]);
      const a = document.createElement("a");
      a.href = record.download_url;
      a.download = record.file_name;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate ZIP archive.");
    } finally {
      setBuildingZip(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">HD Download Manager</h1>
          <p className="mt-1 text-sm text-slate-400">
            Render and download individual 720p / 1080p MP4 shorts or package an entire project as a ZIP archive.
          </p>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {loading ? (
        <div className="h-56 animate-pulse rounded-2xl border border-white/10 bg-[#0d121f]" />
      ) : videos.length === 0 ? (
        <EmptyState
          icon={<Film className="h-6 w-6" />}
          title="No completed projects ready for download"
          description="Upload and process a video (up to 20 minutes) first, then return here to download HD MP4s or ZIP bundles."
          action={
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white"
            >
              Upload Video
            </Link>
          }
        />
      ) : (
        <>
          {/* Batch Controls */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-[#0d121f] p-4">
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs font-medium text-slate-400">Project:</label>
              <select
                value={selectedVideoId}
                onChange={(e) => setSearchParams({ video: e.target.value })}
                className="rounded-xl border border-white/10 bg-[#121829] px-3 py-2 text-sm text-white"
              >
                {videos.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title} ({v.clips_count} shorts)
                  </option>
                ))}
              </select>

              <div className="flex items-center rounded-xl border border-white/10 bg-[#121829] p-1">
                {(["720p", "1080p"] as ExportQuality[]).map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setQuality(q)}
                    className={`rounded-lg px-3 py-1 text-xs font-semibold transition-colors ${
                      quality === q ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {q} HD
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              disabled={buildingZip || clips.length === 0}
              onClick={handleExportZip}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/20 hover:opacity-95 disabled:opacity-50"
            >
              {buildingZip ? <Loader2 className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4" />}
              {buildingZip ? `Rendering & Zipping ${clips.length} Shorts…` : `Download All as ZIP (${quality})`}
            </button>
          </div>

          {/* Individual Clips Table */}
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0d121f]">
            <div className="border-b border-white/10 px-5 py-3.5 text-sm font-semibold text-white">
              Individual Shorts ({clips.length})
            </div>
            <div className="divide-y divide-white/10">
              {clips.map((clip) => {
                const key720 = `720p_${clip.aspect_ratio}`;
                const key1080 = `1080p_${clip.aspect_ratio}`;
                const varSelected = clip.rendered_variants[quality === "1080p" ? key1080 : key720];
                return (
                  <div
                    key={clip.id}
                    className="flex flex-wrap items-center justify-between gap-4 px-5 py-3.5 hover:bg-white/[0.02]"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <img
                        src={clip.thumbnail_url}
                        alt={clip.title}
                        className="h-12 w-16 shrink-0 rounded-lg border border-white/10 object-cover"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-white">
                          #{clip.index} • {clip.title}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                          <span>{clip.duration.toFixed(1)}s</span>
                          <span>•</span>
                          <span>{clip.aspect_ratio}</span>
                          <span>•</span>
                          <span>Score {clip.engagement_score}</span>
                          {varSelected && (
                            <>
                              <span>•</span>
                              <span className="inline-flex items-center gap-1 text-emerald-300">
                                <CheckCircle2 className="h-3 w-3" />
                                Cached ({formatBytes(varSelected.file_size_bytes)})
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        to={`/clips/${clip.id}/edit`}
                        className="rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/5"
                      >
                        Edit
                      </Link>
                      <a
                        href={api.getClipDownloadUrl(clip.id, "720p", clip.aspect_ratio)}
                        className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
                      >
                        <Download className="h-3.5 w-3.5" />
                        720p
                      </a>
                      <a
                        href={api.getClipDownloadUrl(clip.id, "1080p", clip.aspect_ratio)}
                        className="inline-flex items-center gap-1 rounded-lg border border-cyan-500/35 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/25"
                      >
                        <Download className="h-3.5 w-3.5" />
                        1080p
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Export History */}
          {exportsList.length > 0 && (
            <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0d121f]">
              <div className="border-b border-white/10 px-5 py-3.5 text-sm font-semibold text-white">
                Recent Exports
              </div>
              <div className="divide-y divide-white/10">
                {exportsList.map((ex) => (
                  <div key={ex.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-xs">
                    <div>
                      <span className="font-mono font-semibold text-white">{ex.file_name}</span>
                      <span className="ml-2 text-slate-400">
                        ({ex.kind.toUpperCase()} • {ex.quality} • {ex.clip_count} clips • {formatBytes(ex.file_size_bytes)})
                      </span>
                    </div>
                    <a
                      href={ex.download_url}
                      className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-3 py-1.5 font-medium text-cyan-300 hover:bg-white/10"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
