import { Scissors } from "lucide-react";
import { formatTimestampPrecise } from "../../api/client";

interface TrimTimelineProps {
  videoDuration: number;
  originalStart: number;
  originalEnd: number;
  trimStart: number;
  trimEnd: number;
  isFullVideo?: boolean;
  onChange: (newStart: number, newEnd: number) => void;
}

export function TrimTimeline({
  videoDuration,
  originalStart,
  originalEnd,
  trimStart,
  trimEnd,
  isFullVideo = false,
  onChange,
}: TrimTimelineProps) {
  const windowMin = Math.max(0, originalStart - 15);
  const windowMax = Math.min(videoDuration, originalEnd + 15);
  const clipDuration = Math.max(0, trimEnd - trimStart);
  const minGap = isFullVideo ? Math.min(1.0, Math.max(0.5, videoDuration * 0.5)) : 3.0;

  const handleStartSlider = (val: number) => {
    const clamped = Math.min(val, trimEnd - minGap);
    onChange(Number(Math.max(0, clamped).toFixed(2)), trimEnd);
  };

  const handleEndSlider = (val: number) => {
    const clamped = Math.max(val, trimStart + minGap);
    onChange(trimStart, Number(Math.min(videoDuration, clamped).toFixed(2)));
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scissors className="h-4 w-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-white">Clip Trim Timeline</h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-lg bg-violet-500/15 px-2.5 py-1 font-mono text-violet-200">
            Duration: {clipDuration.toFixed(1)}s
          </span>
          <button
            type="button"
            onClick={() => onChange(originalStart, originalEnd)}
            className="rounded-lg border border-white/10 px-2.5 py-1 text-slate-300 hover:bg-white/5"
          >
            {isFullVideo ? "Reset Full Length" : "Reset AI Bounds"}
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <label className="text-slate-400">Start Time</label>
            <span className="font-mono text-slate-200">{formatTimestampPrecise(trimStart)}</span>
          </div>
          <input
            type="range"
            min={windowMin}
            max={Math.max(windowMin + 0.1, trimEnd - minGap)}
            step={0.1}
            value={trimStart}
            onChange={(e) => handleStartSlider(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <label className="text-slate-400">End Time</label>
            <span className="font-mono text-slate-200">{formatTimestampPrecise(trimEnd)}</span>
          </div>
          <input
            type="range"
            min={Math.min(windowMax - 0.1, trimStart + minGap)}
            max={windowMax}
            step={0.1}
            value={trimEnd}
            onChange={(e) => handleEndSlider(parseFloat(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      <p className="text-xs text-slate-400">
        {isFullVideo
          ? `Full source video: ${formatTimestampPrecise(originalStart)} – ${formatTimestampPrecise(originalEnd)}. Trim any section before exporting.`
          : `AI detected window: ${formatTimestampPrecise(originalStart)} – ${formatTimestampPrecise(originalEnd)}. Fine-tune bounds between 3s and 45s.`}
      </p>
    </div>
  );
}
