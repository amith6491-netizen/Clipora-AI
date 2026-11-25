import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Check, Download, Loader2, Save } from "lucide-react";
import { api } from "../api/client";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { StyleControls } from "../components/editor/StyleControls";
import { SubtitleEditor } from "../components/editor/SubtitleEditor";
import { TrimTimeline } from "../components/editor/TrimTimeline";
import { CategoryBadge } from "../components/layout/StatusBadge";
import { ClipPreviewPlayer } from "../components/video/ClipPreviewPlayer";
import type {
  AspectRatio,
  Clip,
  ExportQuality,
  SubtitleCue,
  SubtitleStyle,
  VideoProject,
} from "../types";

export function EditorPage() {
  const { clipId } = useParams<{ clipId: string }>();
  const [clip, setClip] = useState<Clip | null>(null);
  const [video, setVideo] = useState<VideoProject | null>(null);

  const [title, setTitle] = useState("");
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(15);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("9:16");
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle | null>(null);
  const [subtitles, setSubtitles] = useState<SubtitleCue[]>([]);
  const [quality, setQuality] = useState<ExportQuality>("1080p");

  const [seekReq, setSeekReq] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [savedToast, setSavedToast] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clipId) return;
    setLoading(true);
    api
      .getClip(clipId)
      .then(async (c) => {
        const v = await api.getVideo(c.video_id);
        setClip(c);
        setVideo(v);
        setTitle(c.title);
        setTrimStart(c.trim_start);
        setTrimEnd(c.trim_end);
        setAspectRatio(c.aspect_ratio);
        setCaptionsEnabled(c.captions_enabled);
        setSubtitleStyle(c.subtitle_style);
        setSubtitles(c.subtitles);
        setQuality(v.default_quality);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load clip editor.");
      })
      .finally(() => setLoading(false));
  }, [clipId]);

  const saveEdits = async (): Promise<Clip | null> => {
    if (!clip || !subtitleStyle) return null;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateClip(clip.id, {
        title,
        trim_start: trimStart,
        trim_end: trimEnd,
        aspect_ratio: aspectRatio,
        captions_enabled: captionsEnabled,
        subtitle_style: subtitleStyle,
        subtitles,
      });
      setClip(updated);
      setSavedToast(true);
      window.setTimeout(() => setSavedToast(false), 2000);
      return updated;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save edits.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateCaptions = async () => {
    if (!clip) return;
    setRegenerating(true);
    setError(null);
    try {
      await saveEdits();
      const updated = await api.regenerateAutoCaptions(clip.id);
      setClip(updated);
      setCaptionsEnabled(updated.captions_enabled);
      setSubtitles(updated.subtitles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate auto-captions.");
    } finally {
      setRegenerating(false);
    }
  };

  const handleRenderAndDownload = async () => {
    if (!clip) return;
    setRendering(true);
    setError(null);
    try {
      const saved = await saveEdits();
      if (!saved) return;
      const rendered = await api.renderClip(saved.id, quality, aspectRatio);
      setClip(rendered);
      const url = api.getClipDownloadUrl(rendered.id, quality, aspectRatio);
      const a = document.createElement("a");
      a.href = url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to render HD clip.");
    } finally {
      setRendering(false);
    }
  };

  if (loading || !clip || !video || !subtitleStyle) {
    if (error) return <ErrorBanner message={error} />;
    return <div className="h-96 animate-pulse rounded-2xl border border-white/10 bg-[#0d121f]" />;
  }

  return (
    <div className="space-y-6">
      {/* Top Studio Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-[#0d121f] p-4">
        <div className="flex flex-wrap items-center gap-3 min-w-0 flex-1">
          <Link
            to={`/videos/${video.id}/shorts`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Gallery
          </Link>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="min-w-[220px] flex-1 rounded-xl border border-white/10 bg-[#121829] px-3 py-1.5 text-sm font-semibold text-white focus:border-violet-500 focus:outline-none"
          />
          <CategoryBadge category={clip.category} />
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            disabled={saving}
            onClick={saveEdits}
            className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3.5 py-2 text-xs font-semibold text-slate-100 hover:bg-white/10 disabled:opacity-50"
          >
            {savedToast ? <Check className="h-4 w-4 text-emerald-400" /> : <Save className="h-4 w-4" />}
            {saving ? "Saving…" : savedToast ? "Saved" : "Save Edits"}
          </button>

          <select
            value={quality}
            onChange={(e) => setQuality(e.target.value as ExportQuality)}
            className="rounded-xl border border-white/10 bg-[#121829] px-3 py-2 text-xs font-semibold text-white"
          >
            <option value="720p">720p HD</option>
            <option value="1080p">1080p Full HD</option>
          </select>

          <button
            type="button"
            disabled={rendering}
            onClick={handleRenderAndDownload}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-600/20 hover:opacity-95 disabled:opacity-50"
          >
            {rendering ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {rendering ? "Rendering MP4…" : `Export ${quality} MP4`}
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Main Studio Grid */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left: Live Interactive Player + AI Telemetry */}
        <div className="lg:col-span-5 space-y-4">
          <ClipPreviewPlayer
            sourceUrl={video.source_url}
            fallbackPreviewUrl={clip.preview_url}
            trimStart={trimStart}
            trimEnd={trimEnd}
            aspectRatio={aspectRatio}
            captionsEnabled={captionsEnabled}
            subtitleStyle={subtitleStyle}
            subtitles={subtitles}
            seekRequestSec={seekReq}
          />

          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-white">AI Engagement Score</span>
              <span className="font-mono font-bold text-violet-300">{clip.engagement_score}/100</span>
            </div>
            <p className="text-xs text-slate-400">{clip.ai_reason}</p>
          </div>
        </div>

        {/* Right: Trim, Aspect Ratio, Styles & Subtitles */}
        <div className="lg:col-span-7 space-y-4">
          <TrimTimeline
            videoDuration={video.duration}
            originalStart={clip.original_start}
            originalEnd={clip.original_end}
            trimStart={trimStart}
            trimEnd={trimEnd}
            onChange={(s, e) => {
              setTrimStart(s);
              setTrimEnd(e);
            }}
          />

          <StyleControls
            aspectRatio={aspectRatio}
            onChangeAspectRatio={setAspectRatio}
            style={subtitleStyle}
            onChangeStyle={setSubtitleStyle}
          />

          <SubtitleEditor
            captionsEnabled={captionsEnabled}
            onToggleCaptions={setCaptionsEnabled}
            subtitles={subtitles}
            trimStart={trimStart}
            trimEnd={trimEnd}
            onChangeSubtitles={setSubtitles}
            onRegenerateAutoCaptions={handleRegenerateCaptions}
            regenerating={regenerating}
            onSeekToCue={(absSec) => setSeekReq(absSec)}
          />
        </div>
      </div>
    </div>
  );
}
