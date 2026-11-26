import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CheckCircle2,
  Download,
  Edit3,
  Film,
  Instagram,
  Link2,
  Loader2,
  Play,
  Trash2,
} from "lucide-react";
import { api, formatBytes, formatDuration, resolveApiUrl } from "../../api/client";
import type { InstagramDownload } from "../../types";
import { ErrorBanner } from "../common/ErrorBanner";

export function InstagramDownloaderPanel() {
  const [url, setUrl] = useState("");
  const [fetching, setFetching] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [items, setItems] = useState<InstagramDownload[]>([]);
  const [activePreview, setActivePreview] = useState<InstagramDownload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listInstagramDownloads()
      .then((list) => {
        setItems(list);
        if (list.length > 0) setActivePreview(list[0]);
      })
      .catch(() => {})
      .finally(() => setLoadingList(false));
  }, []);

  const handleFetchVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      setError("Please paste an Instagram Reel or video link first.");
      return;
    }
    setError(null);
    setFetching(true);
    try {
      const created = await api.downloadInstagramVideo(url.trim());
      setItems((prev) => [created, ...prev.filter((i) => i.id !== created.id)]);
      setActivePreview(created);
      setUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch Instagram video.");
    } finally {
      setFetching(false);
    }
  };

  const handleDelete = async (itemId: string) => {
    try {
      await api.deleteInstagramDownload(itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
      if (activePreview?.id === itemId) {
        setActivePreview(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove item.");
    }
  };

  const getEditRoute = (item: InstagramDownload): string | null =>
    item.edit_url || (item.clip_id ? `/clips/${item.clip_id}/edit` : null);

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Paste Link Form */}
      <form
        onSubmit={handleFetchVideo}
        className="rounded-2xl border border-white/10 bg-[#0d121f] p-5 sm:p-6 space-y-4"
      >
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-fuchsia-600/30 to-amber-500/30 text-fuchsia-300 ring-1 ring-white/10">
            <Instagram className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">
              Instagram Reel & Video HD Import & Studio
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Paste a public Instagram Reel or video link. Clipora loads it in high quality first so you can preview, open it in Studio Editor (trim, captions, aspect ratio, styles), and download when ready.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Link2 className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-slate-500" />
            <input
              type="url"
              disabled={fetching}
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError(null);
              }}
              placeholder="https://www.instagram.com/reel/..."
              className="w-full rounded-xl border border-white/10 bg-[#121829] py-2.5 pl-10 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-fuchsia-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={fetching || !url.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-fuchsia-600 to-violet-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-fuchsia-600/20 hover:opacity-95 disabled:opacity-40"
          >
            {fetching ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Fetching HD Video…
              </>
            ) : (
              <>
                <Instagram className="h-4 w-4" />
                Fetch Video
              </>
            )}
          </button>
        </div>
      </form>

      {/* Active Preview, Edit & Manual Download Card */}
      {activePreview && (
        <div className="rounded-2xl border border-emerald-500/30 bg-[#0d121f] p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
              <CheckCircle2 className="h-4 w-4" />
              <span>Ready to Edit or Download ({activePreview.width}×{activePreview.height})</span>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              {getEditRoute(activePreview) && (
                <Link
                  to={getEditRoute(activePreview)!}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-600/20 hover:opacity-95"
                >
                  <Edit3 className="h-4 w-4" />
                  Edit Video in Studio
                </Link>
              )}
              <a
                href={resolveApiUrl(activePreview.download_url)}
                download={activePreview.file_name}
                className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-4 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25"
              >
                <Download className="h-4 w-4" />
                Download Original HD ({formatBytes(activePreview.file_size_bytes)})
              </a>
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-12 items-start">
            <div className="md:col-span-5 overflow-hidden rounded-xl border border-white/10 bg-black">
              <video
                key={activePreview.id}
                src={resolveApiUrl(activePreview.preview_url)}
                poster={resolveApiUrl(activePreview.thumbnail_url)}
                controls
                playsInline
                className="max-h-96 w-full object-contain"
              />
            </div>

            <div className="md:col-span-7 space-y-3">
              <h3 className="text-base font-semibold text-white">{activePreview.title}</h3>
              <p className="text-xs text-slate-400">Creator: {activePreview.author}</p>
              <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/10 bg-[#121829] p-3 text-xs">
                <div>
                  <div className="text-slate-400">Resolution</div>
                  <div className="font-mono font-semibold text-white">
                    {activePreview.width}×{activePreview.height}
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">Duration</div>
                  <div className="font-mono font-semibold text-white">
                    {formatDuration(activePreview.duration)}
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">File Size</div>
                  <div className="font-mono font-semibold text-white">
                    {formatBytes(activePreview.file_size_bytes)}
                  </div>
                </div>
              </div>
              <p className="truncate font-mono text-[11px] text-slate-500">{activePreview.file_name}</p>
            </div>
          </div>
        </div>
      )}

      {/* History List */}
      {!loadingList && items.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0d121f]">
          <div className="border-b border-white/10 px-5 py-3.5 text-sm font-semibold text-white">
            Fetched Instagram Videos ({items.length})
          </div>
          <div className="divide-y divide-white/10">
            {items.map((item) => {
              const editRoute = getEditRoute(item);
              return (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-4 px-5 py-3.5 hover:bg-white/[0.02]"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <img
                      src={resolveApiUrl(item.thumbnail_url)}
                      alt={item.title}
                      className="h-14 w-12 shrink-0 rounded-lg border border-white/10 bg-black object-cover"
                    />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-white">{item.title}</div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                        <span>{item.author}</span>
                        <span>•</span>
                        <span>{item.width}×{item.height}</span>
                        <span>•</span>
                        <span>{formatDuration(item.duration)}</span>
                        <span>•</span>
                        <span>{formatBytes(item.file_size_bytes)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setActivePreview(item)}
                      className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
                    >
                      <Play className="h-3.5 w-3.5" />
                      Preview
                    </button>
                    {editRoute && (
                      <Link
                        to={editRoute}
                        className="inline-flex items-center gap-1 rounded-lg border border-violet-500/40 bg-violet-500/15 px-3 py-1.5 text-xs font-semibold text-violet-200 hover:bg-violet-500/25"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                        Edit
                      </Link>
                    )}
                    <a
                      href={resolveApiUrl(item.download_url)}
                      download={item.file_name}
                      className="inline-flex items-center gap-1 rounded-lg border border-cyan-500/35 bg-cyan-500/15 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/25"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download MP4
                    </a>
                    <button
                      type="button"
                      onClick={() => handleDelete(item.id)}
                      className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/15 hover:text-rose-300"
                      aria-label="Delete Instagram video"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!loadingList && items.length === 0 && !activePreview && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-[#0d121f]/60 py-10 text-center">
          <Film className="h-7 w-7 text-slate-500" />
          <p className="mt-2 text-sm text-slate-400">
            No Instagram videos loaded yet. Paste a public Reel link above to preview, edit, and download in HD.
          </p>
        </div>
      )}
    </div>
  );
}
