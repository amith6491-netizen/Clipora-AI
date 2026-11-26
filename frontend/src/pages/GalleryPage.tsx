import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Download,
  Edit3,
  Eye,
  Film,
  Flame,
  PackageOpen,
  UploadCloud,
  X,
} from "lucide-react";
import { api, CATEGORY_META, formatTimestampPrecise, resolveApiUrl } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { CategoryBadge } from "../components/layout/StatusBadge";
import { ClipPreviewPlayer } from "../components/video/ClipPreviewPlayer";
import type { Clip, MomentCategory, VideoProject } from "../types";

const CATEGORIES: (MomentCategory | "all")[] = [
  "all",
  "interesting",
  "funny",
  "important",
  "motivational",
  "educational",
  "engaging",
];

export function GalleryPage() {
  const { videoId: routeVideoId } = useParams<{ videoId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [activeVideoId, setActiveVideoId] = useState<string>(
    routeVideoId || searchParams.get("video") || ""
  );
  const [video, setVideo] = useState<VideoProject | null>(null);
  const [clips, setClips] = useState<Clip[]>([]);
  const [category, setCategory] = useState<MomentCategory | "all">("all");
  const [sortBy, setSortBy] = useState<"score" | "timeline" | "duration">("score");
  const [previewClip, setPreviewClip] = useState<Clip | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (routeVideoId) {
      setActiveVideoId(routeVideoId);
      return;
    }
    const qVid = searchParams.get("video");
    if (qVid) setActiveVideoId(qVid);
  }, [routeVideoId, searchParams]);

  useEffect(() => {
    api
      .listVideos()
      .then((list) => {
        setProjects(list);
        if (!routeVideoId && !searchParams.get("video") && list.length > 0) {
          const preferred = list.find((v) => v.clips_count > 0) || list[0];
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
    setLoading(true);
    Promise.all([api.getVideo(activeVideoId), api.listClips(activeVideoId, category, sortBy)])
      .then(([vid, clipList]) => {
        setVideo(vid);
        setClips(clipList);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load generated shorts.");
      })
      .finally(() => setLoading(false));
  }, [activeVideoId, category, sortBy]);

  const handleSelectProject = (newId: string) => {
    setActiveVideoId(newId);
    if (routeVideoId) {
      navigate(`/videos/${newId}/shorts`);
    } else {
      setSearchParams({ video: newId });
    }
  };

  if (!loading && !activeVideoId) {
    return (
      <EmptyState
        icon={<Film className="h-6 w-6" />}
        title="No generated shorts yet"
        description="Upload a video file or paste a YouTube link to generate 5–15 AI-ranked shorts."
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
          <h1 className="text-2xl font-bold text-white">Generated Shorts Gallery</h1>
          <p className="mt-1 text-sm text-slate-400">
            {video ? `${video.title} • ${clips.length} AI-ranked short clips` : "AI-ranked shorts"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {projects.length > 0 && (
            <select
              value={activeVideoId}
              onChange={(e) => handleSelectProject(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#121829] px-3 py-2 text-xs text-white"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.clips_count} shorts)
                </option>
              ))}
            </select>
          )}
          <Link
            to={`/videos/${activeVideoId}/processing`}
            className="rounded-xl border border-white/10 bg-white/5 px-3.5 py-2 text-xs font-medium text-slate-200 hover:bg-white/10"
          >
            Analysis Logs
          </Link>
          <Link
            to={`/downloads?video=${activeVideoId}`}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-600/20"
          >
            <PackageOpen className="h-4 w-4" />
            Download All / ZIP
          </Link>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Filter & Sort Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-[#0d121f] p-3.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {CATEGORIES.map((cat) => {
            const active = category === cat;
            return (
              <button
                key={cat}
                type="button"
                onClick={() => setCategory(cat)}
                className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                  active
                    ? "bg-violet-600 text-white"
                    : "bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                {cat === "all" ? "All Moments" : CATEGORY_META[cat].label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as "score" | "timeline" | "duration")}
            className="rounded-xl border border-white/10 bg-[#121829] px-3 py-1.5 text-slate-200 focus:border-violet-500 focus:outline-none"
          >
            <option value="score">AI Engagement Score</option>
            <option value="timeline">Video Timeline</option>
            <option value="duration">Clip Duration</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-80 animate-pulse rounded-2xl border border-white/10 bg-[#0d121f]" />
          ))}
        </div>
      ) : clips.length === 0 ? (
        <EmptyState
          icon={<Film className="h-6 w-6" />}
          title="No clips match this filter"
          description="Try selecting All Moments, switching projects above, or checking AI Analysis Process."
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {clips.map((clip) => (
            <article
              key={clip.id}
              className="flex flex-col justify-between overflow-hidden rounded-2xl border border-white/10 bg-[#0d121f] transition-colors hover:border-violet-500/40"
            >
              <div>
                <div className="relative h-44 bg-black">
                  <img
                    src={resolveApiUrl(clip.thumbnail_url)}
                    alt={clip.title}
                    className="h-full w-full object-cover opacity-90"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0d121f] via-transparent to-black/40" />
                  <div className="absolute top-3 left-3 flex items-center gap-1.5">
                    <span className="rounded-lg bg-black/70 px-2 py-0.5 font-mono text-xs font-semibold text-white">
                      #{clip.index}
                    </span>
                    <CategoryBadge category={clip.category} />
                  </div>
                  <div className="absolute top-3 right-3 flex items-center gap-1 rounded-lg bg-violet-600/90 px-2.5 py-0.5 text-xs font-bold text-white shadow">
                    <Flame className="h-3.5 w-3.5" />
                    {clip.engagement_score.toFixed(0)}
                  </div>
                  <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between text-xs text-slate-200 font-mono">
                    <span>
                      {formatTimestampPrecise(clip.trim_start)} – {formatTimestampPrecise(clip.trim_end)}
                    </span>
                    <span className="rounded bg-black/70 px-1.5 py-0.5">
                      {clip.duration.toFixed(1)}s • {clip.aspect_ratio}
                    </span>
                  </div>
                </div>

                <div className="p-4 space-y-3">
                  <h2 className="line-clamp-2 text-base font-semibold text-white">{clip.title}</h2>
                  <p className="line-clamp-2 text-xs text-slate-300/90">“{clip.transcript_text}”</p>
                  <p className="text-[11px] text-slate-400">{clip.ai_reason}</p>

                  {/* Mini Score Breakdown */}
                  <div className="grid grid-cols-4 gap-2 rounded-xl border border-white/5 bg-[#121829] p-2.5 text-center text-[11px]">
                    <div>
                      <div className="text-slate-400">NLP</div>
                      <div className="font-mono font-semibold text-violet-300">
                        {clip.score_breakdown.nlp_score.toFixed(0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-400">Audio</div>
                      <div className="font-mono font-semibold text-cyan-300">
                        {clip.score_breakdown.audio_score.toFixed(0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-400">Visual</div>
                      <div className="font-mono font-semibold text-emerald-300">
                        {clip.score_breakdown.visual_score.toFixed(0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-400">Hook</div>
                      <div className="font-mono font-semibold text-amber-300">
                        {clip.score_breakdown.hook_score.toFixed(0)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-4 py-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPreviewClip(clip)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    Preview
                  </button>
                  <Link
                    to={`/clips/${clip.id}/edit`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-500"
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                    Edit
                  </Link>
                </div>

                <a
                  href={api.getClipDownloadUrl(clip.id, "1080p", clip.aspect_ratio)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-500/35 bg-cyan-500/15 px-2.5 py-1.5 text-xs font-medium text-cyan-200 hover:bg-cyan-500/25"
                >
                  <Download className="h-3.5 w-3.5" />
                  1080p MP4
                </a>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Quick Preview Modal */}
      {previewClip && video && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-2xl border border-white/15 bg-[#0d121f] p-5 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">{previewClip.title}</h3>
                <p className="text-xs text-slate-400">
                  Engagement Score: {previewClip.engagement_score}/100 • {previewClip.aspect_ratio}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewClip(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
                aria-label="Close preview"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <ClipPreviewPlayer
              sourceUrl={resolveApiUrl(video.source_url)}
              fallbackPreviewUrl={resolveApiUrl(previewClip.preview_url)}
              trimStart={previewClip.trim_start}
              trimEnd={previewClip.trim_end}
              aspectRatio={previewClip.aspect_ratio}
              captionsEnabled={previewClip.captions_enabled}
              subtitleStyle={previewClip.subtitle_style}
              subtitles={previewClip.subtitles}
            />

            <div className="flex items-center justify-end gap-3 pt-2">
              <Link
                to={`/clips/${previewClip.id}/edit`}
                className="rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white hover:bg-violet-500"
              >
                Open in Video Editor
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
