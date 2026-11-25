import { Palette, Ratio } from "lucide-react";
import { SUBTITLE_PRESETS } from "../../api/client";
import type { AspectRatio, SubtitlePosition, SubtitlePreset, SubtitleStyle } from "../../types";

interface StyleControlsProps {
  aspectRatio: AspectRatio;
  onChangeAspectRatio: (ar: AspectRatio) => void;
  style: SubtitleStyle;
  onChangeStyle: (style: SubtitleStyle) => void;
}

export function StyleControls({
  aspectRatio,
  onChangeAspectRatio,
  style,
  onChangeStyle,
}: StyleControlsProps) {
  const aspectOptions: { value: AspectRatio; label: string; hint: string }[] = [
    { value: "9:16", label: "9:16 Vertical", hint: "Reels / Shorts / TikTok" },
    { value: "16:9", label: "16:9 Widescreen", hint: "YouTube / Desktop" },
    { value: "1:1", label: "1:1 Square", hint: "LinkedIn / Feed" },
  ];

  const applyPreset = (preset: SubtitlePreset) => {
    onChangeStyle({
      ...style,
      ...SUBTITLE_PRESETS[preset].defaults,
      preset,
    });
  };

  return (
    <div className="space-y-4">
      {/* Aspect Ratio */}
      <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Ratio className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">Aspect Ratio</h3>
        </div>
        <div className="grid grid-cols-3 gap-2.5">
          {aspectOptions.map((opt) => {
            const active = aspectRatio === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onChangeAspectRatio(opt.value)}
                className={`rounded-xl border p-2.5 text-left transition-all ${
                  active
                    ? "border-violet-500 bg-violet-500/15 text-white"
                    : "border-white/10 bg-[#121829] text-slate-300 hover:border-white/25"
                }`}
              >
                <div className="text-xs font-bold">{opt.label}</div>
                <div className="mt-0.5 text-[11px] text-slate-400">{opt.hint}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Subtitle Styles & Colors */}
      <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-white">Caption Style & Colors</h3>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {(Object.keys(SUBTITLE_PRESETS) as SubtitlePreset[]).map((key) => {
            const p = SUBTITLE_PRESETS[key];
            const active = style.preset === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => applyPreset(key)}
                className={`rounded-xl border p-2.5 text-left transition-all ${
                  active
                    ? "border-violet-500 bg-violet-500/15"
                    : "border-white/10 bg-[#121829] hover:border-white/25"
                }`}
              >
                <div className="text-xs font-semibold text-white">{p.label}</div>
                <div className="mt-0.5 line-clamp-1 text-[11px] text-slate-400">{p.description}</div>
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <label className="space-y-1 text-xs text-slate-300">
            <span>Text Color</span>
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#121829] p-1.5">
              <input
                type="color"
                value={style.text_color}
                onChange={(e) => onChangeStyle({ ...style, text_color: e.target.value })}
                className="h-6 w-7 cursor-pointer rounded border-0 bg-transparent"
              />
              <span className="font-mono text-[11px]">{style.text_color}</span>
            </div>
          </label>

          <label className="space-y-1 text-xs text-slate-300">
            <span>Accent Color</span>
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#121829] p-1.5">
              <input
                type="color"
                value={style.accent_color}
                onChange={(e) => onChangeStyle({ ...style, accent_color: e.target.value })}
                className="h-6 w-7 cursor-pointer rounded border-0 bg-transparent"
              />
              <span className="font-mono text-[11px]">{style.accent_color}</span>
            </div>
          </label>

          <label className="space-y-1 text-xs text-slate-300">
            <span>Box Color</span>
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#121829] p-1.5">
              <input
                type="color"
                value={style.background_color}
                onChange={(e) => onChangeStyle({ ...style, background_color: e.target.value })}
                className="h-6 w-7 cursor-pointer rounded border-0 bg-transparent"
              />
              <span className="font-mono text-[11px]">{style.background_color}</span>
            </div>
          </label>

          <label className="space-y-1 text-xs text-slate-300">
            <span>Outline Color</span>
            <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#121829] p-1.5">
              <input
                type="color"
                value={style.outline_color}
                onChange={(e) => onChangeStyle({ ...style, outline_color: e.target.value })}
                className="h-6 w-7 cursor-pointer rounded border-0 bg-transparent"
              />
              <span className="font-mono text-[11px]">{style.outline_color}</span>
            </div>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Font Size</span>
              <span className="font-mono">{style.font_size}px</span>
            </div>
            <input
              type="range"
              min={18}
              max={64}
              value={style.font_size}
              onChange={(e) => onChangeStyle({ ...style, font_size: Number(e.target.value) })}
              className="w-full"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Box Opacity</span>
              <span className="font-mono">{Math.round(style.background_opacity * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={style.background_opacity}
              onChange={(e) => onChangeStyle({ ...style, background_opacity: Number(e.target.value) })}
              className="w-full"
            />
          </div>

          <div className="space-y-1">
            <span className="text-xs text-slate-300">Position</span>
            <div className="grid grid-cols-3 gap-1">
              {(["bottom", "center", "top"] as SubtitlePosition[]).map((pos) => (
                <button
                  key={pos}
                  type="button"
                  onClick={() => onChangeStyle({ ...style, position: pos })}
                  className={`rounded-lg border py-1 text-xs capitalize ${
                    style.position === pos
                      ? "border-violet-500 bg-violet-500/20 text-white"
                      : "border-white/10 bg-[#121829] text-slate-400"
                  }`}
                >
                  {pos}
                </button>
              ))}
            </div>
          </div>
        </div>

        <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={style.uppercase}
            onChange={(e) => onChangeStyle({ ...style, uppercase: e.target.checked })}
            className="h-4 w-4 rounded accent-violet-500"
          />
          ALL CAPS captions
        </label>
      </div>
    </div>
  );
}
