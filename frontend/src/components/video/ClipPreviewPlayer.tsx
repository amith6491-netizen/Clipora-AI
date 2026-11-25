import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RotateCcw, Volume2, VolumeX } from "lucide-react";
import type { AspectRatio, SubtitleCue, SubtitleStyle } from "../../types";

interface ClipPreviewPlayerProps {
  sourceUrl: string;
  fallbackPreviewUrl?: string;
  trimStart: number;
  trimEnd: number;
  aspectRatio: AspectRatio;
  captionsEnabled: boolean;
  subtitleStyle: SubtitleStyle;
  subtitles: SubtitleCue[];
  seekRequestSec?: number | null;
}

export function ClipPreviewPlayer({
  sourceUrl,
  fallbackPreviewUrl,
  trimStart,
  trimEnd,
  aspectRatio,
  captionsEnabled,
  subtitleStyle,
  subtitles,
  seekRequestSec,
}: ClipPreviewPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [useFallback, setUseFallback] = useState(false);
  const [currentTime, setCurrentTime] = useState(trimStart);

  useEffect(() => {
    setUseFallback(false);
  }, [sourceUrl, fallbackPreviewUrl]);

  const activeStart = useFallback ? 0 : trimStart;
  const activeEnd = useFallback ? Math.max(0.5, trimEnd - trimStart) : trimEnd;
  const clipDuration = Math.max(0.5, trimEnd - trimStart);

  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;
    if (vid.currentTime < activeStart || vid.currentTime > activeEnd) {
      vid.currentTime = activeStart;
      setCurrentTime(trimStart);
    }
  }, [activeStart, activeEnd, trimStart]);

  useEffect(() => {
    if (seekRequestSec === null || seekRequestSec === undefined) return;
    const vid = videoRef.current;
    if (!vid) return;
    const clampedAbs = Math.max(trimStart, Math.min(trimEnd - 0.05, seekRequestSec));
    vid.currentTime = useFallback ? clampedAbs - trimStart : clampedAbs;
    setCurrentTime(clampedAbs);
  }, [seekRequestSec, trimStart, trimEnd, useFallback]);

  const activeCue = useMemo(() => {
    if (!captionsEnabled || useFallback) return null;
    return subtitles.find((c) => currentTime >= c.start && currentTime <= c.end) ?? null;
  }, [captionsEnabled, subtitles, currentTime, useFallback]);

  const togglePlay = () => {
    const vid = videoRef.current;
    if (!vid) return;
    if (vid.paused) {
      if (vid.currentTime < activeStart || vid.currentTime >= activeEnd - 0.05) {
        vid.currentTime = activeStart;
      }
      vid.play().catch(() => { });
    } else {
      vid.pause();
    }
  };

  const handleTimeUpdate = () => {
    const vid = videoRef.current;
    if (!vid) return;
    if (vid.currentTime >= activeEnd) {
      vid.currentTime = activeStart;
      setCurrentTime(trimStart);
      if (!vid.paused) {
        vid.play().catch(() => { });
      }
    } else if (vid.currentTime < activeStart) {
      vid.currentTime = activeStart;
      setCurrentTime(trimStart);
    } else {
      setCurrentTime(useFallback ? trimStart + vid.currentTime : vid.currentTime);
    }
  };

  const relProgress = Math.max(0, Math.min(100, ((currentTime - trimStart) / clipDuration) * 100));

  const frameAspectClass =
    aspectRatio === "9:16"
      ? "aspect-[9/16] max-h-[520px]"
      : aspectRatio === "1:1"
        ? "aspect-square max-h-[460px]"
        : "aspect-video w-full max-h-[420px]";

  const posClass =
    subtitleStyle.position === "top"
      ? "top-6"
      : subtitleStyle.position === "center"
        ? "top-1/2 -translate-y-1/2"
        : "bottom-7";

  const hexToRgba = (hex: string, alpha: number) => {
    const clean = hex.replace("#", "");
    if (clean.length !== 6) return `rgba(0,0,0,${alpha})`;
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const useBox = subtitleStyle.preset === "neon_box" || subtitleStyle.preset === "bold_pop";
  const scaledFontPx = Math.max(13, Math.round(subtitleStyle.font_size * 0.56));

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        onClick={togglePlay}
        className={`relative mx-auto overflow-hidden rounded-2xl border border-white/15 bg-black shadow-2xl shadow-black/60 cursor-pointer flex items-center justify-center ${frameAspectClass}`}
      >
        <video
          ref={videoRef}
          src={useFallback && fallbackPreviewUrl ? fallbackPreviewUrl : sourceUrl}
          muted={muted}
          playsInline
          onLoadedMetadata={() => {
            if (videoRef.current) {
              videoRef.current.currentTime = activeStart;
              setCurrentTime(trimStart);
            }
          }}
          onError={() => {
            if (!useFallback && fallbackPreviewUrl) {
              setUseFallback(true);
            }
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={handleTimeUpdate}
          className="h-full w-full object-cover"
        />

        {/* Aspect ratio badge */}
        <span className="pointer-events-none absolute top-3 left-3 rounded-md bg-black/60 px-2 py-0.5 text-[11px] font-mono font-medium text-slate-200 backdrop-blur-sm">
          {aspectRatio}
        </span>

        {/* Live Subtitle Overlay */}
        {activeCue && (
          <div className={`pointer-events-none absolute inset-x-4 flex justify-center ${posClass}`}>
            <div
              className="max-w-[92%] rounded-lg px-3 py-1.5 text-center leading-snug transition-all"
              style={{
                color: subtitleStyle.text_color,
                backgroundColor: useBox
                  ? hexToRgba(subtitleStyle.background_color, subtitleStyle.background_opacity)
                  : subtitleStyle.background_opacity > 0.05
                    ? hexToRgba(subtitleStyle.background_color, subtitleStyle.background_opacity * 0.6)
                    : "transparent",
                fontSize: `${scaledFontPx}px`,
                fontWeight: subtitleStyle.preset === "minimal_clean" ? 600 : 800,
                textTransform: subtitleStyle.uppercase ? "uppercase" : "none",
                textShadow: `0 2px 4px ${subtitleStyle.outline_color}, 0 0 2px ${subtitleStyle.outline_color}`,
                border:
                  subtitleStyle.preset === "neon_box"
                    ? `1px solid ${subtitleStyle.accent_color}`
                    : "none",
              }}
            >
              {activeCue.text}
            </div>
          </div>
        )}

        {!playing && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/25">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-violet-600/90 text-white shadow-lg">
              <Play className="ml-0.5 h-6 w-6 fill-current" />
            </div>
          </div>
        )}
      </div>

      {/* Transport & Scrub Controls */}
      <div className="w-full rounded-xl border border-white/10 bg-[#0d121f] px-3.5 py-2.5 space-y-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={togglePlay}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 text-white hover:bg-violet-500 transition-colors"
            aria-label={playing ? "Pause preview" : "Play preview"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
          </button>

          <button
            type="button"
            onClick={() => {
              if (videoRef.current) {
                videoRef.current.currentTime = activeStart;
                setCurrentTime(trimStart);
              }
            }}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-slate-300 hover:bg-white/5"
            aria-label="Restart clip"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          <div className="flex-1">
            <input
              type="range"
              min={0}
              max={100}
              step={0.5}
              value={relProgress}
              onChange={(e) => {
                const pct = parseFloat(e.target.value);
                const relTarget = (pct / 100) * clipDuration;
                if (videoRef.current) {
                  videoRef.current.currentTime = useFallback ? relTarget : trimStart + relTarget;
                  setCurrentTime(trimStart + relTarget);
                }
              }}
              className="w-full cursor-pointer"
            />
          </div>

          <span className="font-mono text-xs text-slate-300">
            {(currentTime - trimStart).toFixed(1)}s / {clipDuration.toFixed(1)}s
          </span>

          <button
            type="button"
            onClick={() => setMuted((m) => !m)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-slate-300 hover:bg-white/5"
            aria-label={muted ? "Unmute" : "Mute"}
          >
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
