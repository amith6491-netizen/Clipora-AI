import { CATEGORY_META } from "../../api/client";
import type { MomentCategory, VideoStatus } from "../../types";

export function VideoStatusBadge({ status }: { status: VideoStatus }) {
  const map: Record<VideoStatus, { label: string; classes: string; dot: string }> = {
    uploaded: {
      label: "Uploaded",
      classes: "bg-slate-500/15 text-slate-300 border-slate-500/30",
      dot: "bg-slate-400",
    },
    queued: {
      label: "Queued",
      classes: "bg-amber-500/15 text-amber-300 border-amber-500/30",
      dot: "bg-amber-400 animate-pulse",
    },
    processing: {
      label: "AI Analyzing",
      classes: "bg-violet-500/15 text-violet-300 border-violet-500/30",
      dot: "bg-violet-400 animate-ping",
    },
    completed: {
      label: "Ready",
      classes: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
      dot: "bg-emerald-400",
    },
    failed: {
      label: "Failed",
      classes: "bg-rose-500/15 text-rose-300 border-rose-500/30",
      dot: "bg-rose-400",
    },
    cancelled: {
      label: "Cancelled",
      classes: "bg-slate-500/15 text-slate-300 border-slate-500/30",
      dot: "bg-slate-400",
    },
  };

  const item = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${item.classes}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${item.dot}`} />
      {item.label}
    </span>
  );
}

export function CategoryBadge({ category }: { category: MomentCategory }) {
  const meta = CATEGORY_META[category];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${meta.bgClass} ${meta.colorClass} ${meta.borderClass}`}
    >
      {meta.label}
    </span>
  );
}
