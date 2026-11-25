import { Plus, Sparkles, Trash2 } from "lucide-react";
import type { SubtitleCue } from "../../types";

interface SubtitleEditorProps {
  captionsEnabled: boolean;
  onToggleCaptions: (enabled: boolean) => void;
  subtitles: SubtitleCue[];
  trimStart: number;
  trimEnd: number;
  onChangeSubtitles: (cues: SubtitleCue[]) => void;
  onRegenerateAutoCaptions: () => void;
  regenerating: boolean;
  onSeekToCue: (absSec: number) => void;
}

export function SubtitleEditor({
  captionsEnabled,
  onToggleCaptions,
  subtitles,
  trimStart,
  trimEnd,
  onChangeSubtitles,
  onRegenerateAutoCaptions,
  regenerating,
  onSeekToCue,
}: SubtitleEditorProps) {
  const handleCueChange = (id: string, patch: Partial<SubtitleCue>) => {
    onChangeSubtitles(
      subtitles.map((cue) => (cue.id === id ? { ...cue, ...patch } : cue))
    );
  };

  const handleAddCue = () => {
    const lastEnd = subtitles.length > 0 ? subtitles[subtitles.length - 1].end : trimStart;
    const start = Math.min(trimEnd - 0.5, Math.max(trimStart, lastEnd));
    const end = Math.min(trimEnd, start + 2.0);
    const next: SubtitleCue = {
      id: `cue-${Date.now()}`,
      start: Number(start.toFixed(2)),
      end: Number(Math.max(start + 0.3, end).toFixed(2)),
      text: "New caption line",
    };
    onChangeSubtitles([...subtitles, next]);
  };

  const handleRemoveCue = (id: string) => {
    onChangeSubtitles(subtitles.filter((c) => c.id !== id));
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-white">Subtitles & Auto-Captions</h3>
          <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={captionsEnabled}
              onChange={(e) => onToggleCaptions(e.target.checked)}
              className="h-4 w-4 rounded border-white/20 bg-slate-900 accent-violet-500"
            />
            Burn captions into video
          </label>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={regenerating}
            onClick={onRegenerateAutoCaptions}
            className="inline-flex items-center gap-1.5 rounded-lg border border-violet-500/40 bg-violet-500/15 px-3 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/25 disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {regenerating ? "Syncing…" : "Auto-Captions"}
          </button>
          <button
            type="button"
            onClick={handleAddCue}
            className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Cue
          </button>
        </div>
      </div>

      {subtitles.length === 0 ? (
        <p className="rounded-xl border border-dashed border-white/10 py-6 text-center text-xs text-slate-400">
          No subtitle cues yet. Click <strong>Auto-Captions</strong> to sync captions from Faster-Whisper or add cues manually.
        </p>
      ) : (
        <div className="max-h-72 space-y-2.5 overflow-y-auto pr-1">
          {subtitles.map((cue, idx) => {
            const relStart = Math.max(0, cue.start - trimStart);
            const relEnd = Math.max(0.1, cue.end - trimStart);
            return (
              <div
                key={cue.id}
                className="rounded-xl border border-white/10 bg-[#121829] p-3 space-y-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => onSeekToCue(cue.start)}
                    className="font-mono text-violet-300 hover:underline"
                  >
                    #{idx + 1} • {relStart.toFixed(1)}s → {relEnd.toFixed(1)}s
                  </button>
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-slate-400">
                      Start
                      <input
                        type="number"
                        step={0.1}
                        min={0}
                        max={Math.max(0.1, relEnd - 0.1)}
                        value={Number(relStart.toFixed(2))}
                        onChange={(e) => {
                          const nextAbs = trimStart + Math.max(0, parseFloat(e.target.value) || 0);
                          handleCueChange(cue.id, {
                            start: Number(Math.min(cue.end - 0.1, nextAbs).toFixed(3)),
                          });
                        }}
                        className="w-16 rounded border border-white/10 bg-[#0b0f19] px-1.5 py-0.5 font-mono text-slate-200"
                      />
                    </label>
                    <label className="flex items-center gap-1 text-slate-400">
                      End
                      <input
                        type="number"
                        step={0.1}
                        min={relStart + 0.1}
                        max={Math.max(1, trimEnd - trimStart)}
                        value={Number(relEnd.toFixed(2))}
                        onChange={(e) => {
                          const nextAbs = trimStart + Math.max(relStart + 0.1, parseFloat(e.target.value) || 0.2);
                          handleCueChange(cue.id, {
                            end: Number(Math.min(trimEnd, nextAbs).toFixed(3)),
                          });
                        }}
                        className="w-16 rounded border border-white/10 bg-[#0b0f19] px-1.5 py-0.5 font-mono text-slate-200"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => handleRemoveCue(cue.id)}
                      className="rounded p-1 text-slate-400 hover:bg-rose-500/15 hover:text-rose-300"
                      aria-label="Delete cue"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={cue.text}
                  onChange={(e) => handleCueChange(cue.id, { text: e.target.value })}
                  className="w-full rounded-lg border border-white/10 bg-[#0b0f19] px-3 py-1.5 text-sm text-slate-100 focus:border-violet-500 focus:outline-none"
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
