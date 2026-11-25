import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileVideo, UploadCloud, X, AlertCircle } from "lucide-react";
import { formatBytes, formatDuration } from "../../api/client";

const ALLOWED_EXTENSIONS = [".mp4", ".mov", ".mkv", ".webm"];

interface DropZoneUploaderProps {
  minDurationSec: number;
  maxDurationSec: number;
  selectedFile: File | null;
  onFileSelected: (file: File | null, detectedDuration: number | null) => void;
  uploading: boolean;
  progressPercent: number;
  uploadSpeedBytesPerSec: number;
  uploadedBytes: number;
  totalBytes: number;
  onCancelUpload?: () => void;
}

export function DropZoneUploader({
  minDurationSec,
  maxDurationSec,
  selectedFile,
  onFileSelected,
  uploading,
  progressPercent,
  uploadSpeedBytesPerSec,
  uploadedBytes,
  totalBytes,
  onCancelUpload,
}: DropZoneUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [detectedDuration, setDetectedDuration] = useState<number | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [previewUnsupported, setPreviewUnsupported] = useState(false);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      setDetectedDuration(null);
      setPreviewUnsupported(false);
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    setPreviewUnsupported(false);
    return () => URL.revokeObjectURL(url);
  }, [selectedFile]);

  const validateAndAccept = (file: File) => {
    setClientError(null);
    const lowerName = file.name.toLowerCase();
    const ext = lowerName.slice(lowerName.lastIndexOf("."));
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setClientError(
        `Unsupported file format "${ext || "unknown"}". Please select an MP4, MOV, MKV, or WebM video.`
      );
      onFileSelected(null, null);
      return;
    }
    setDetectedDuration(null);
    onFileSelected(file, null);
  };

  const handleVideoMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const dur = e.currentTarget.duration;
    if (!Number.isFinite(dur) || dur <= 0) return;
    setDetectedDuration(dur);
    if (dur < minDurationSec || dur > maxDurationSec) {
      setClientError(
        `Video duration is ${formatDuration(dur)} (${dur.toFixed(0)}s). Uploaded videos must be under ${formatDuration(maxDurationSec)} (at least ${formatDuration(minDurationSec)}).`
      );
    } else {
      setClientError(null);
    }
    if (selectedFile) {
      onFileSelected(selectedFile, dur);
    }
  };

  const durationValid =
    detectedDuration === null ||
    (detectedDuration >= minDurationSec && detectedDuration <= maxDurationSec);

  return (
    <div className="space-y-4">
      {!selectedFile ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const dropped = e.dataTransfer.files?.[0];
            if (dropped) validateAndAccept(dropped);
          }}
          onClick={() => inputRef.current?.click()}
          className={`group cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all ${
            dragOver
              ? "border-violet-400 bg-violet-500/10"
              : "border-white/15 bg-[#0d121f]/80 hover:border-violet-500/60 hover:bg-[#111729]"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".mp4,.mov,.mkv,.webm,video/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) validateAndAccept(file);
            }}
          />
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600/30 to-cyan-500/30 text-violet-300 ring-1 ring-white/10 group-hover:scale-105 transition-transform">
            <UploadCloud className="h-7 w-7" />
          </div>
          <h3 className="text-lg font-semibold text-white">
            Drag & drop your long-form video here
          </h3>
          <p className="mt-1.5 text-sm text-slate-400">
            or <span className="text-violet-400 font-medium underline underline-offset-4">browse files</span> from your computer
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-400">
            <span className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1">
              MP4, MOV, MKV, WebM
            </span>
            <span className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1">
              Duration: Under {Math.round(maxDurationSec / 60)} minutes (min {Math.round(minDurationSec)}s)
            </span>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-4 sm:p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300">
                <FileVideo className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{selectedFile.name}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span>{formatBytes(selectedFile.size)}</span>
                  {detectedDuration !== null && (
                    <>
                      <span>•</span>
                      <span className={durationValid ? "text-emerald-300" : "text-rose-300 font-medium"}>
                        Duration: {formatDuration(detectedDuration)}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {!uploading && (
              <button
                type="button"
                onClick={() => {
                  setClientError(null);
                  onFileSelected(null, null);
                }}
                className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/5"
              >
                <X className="h-3.5 w-3.5" />
                Change Video
              </button>
            )}
          </div>

          {/* Interactive Video Preview */}
          {previewUrl && !previewUnsupported ? (
            <div className="overflow-hidden rounded-xl border border-white/10 bg-black">
              <video
                src={previewUrl}
                controls
                preload="metadata"
                onLoadedMetadata={handleVideoMetadata}
                onError={() => setPreviewUnsupported(true)}
                className="max-h-72 w-full object-contain"
              />
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-[#080b12] px-4 py-6 text-center text-xs text-slate-400">
              Browser inline preview is unavailable for this container codec (e.g. MKV). Server-side FFprobe will validate duration and generate a preview frame upon upload.
            </div>
          )}

          {detectedDuration !== null && durationValid && (
            <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>Format and duration validated ({formatDuration(detectedDuration)}). Ready for AI shorts extraction.</span>
            </div>
          )}

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="space-y-2 rounded-xl border border-violet-500/30 bg-violet-500/10 p-3.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-violet-200">
                  Uploading video… {progressPercent}%
                </span>
                <span className="text-slate-300 font-mono">
                  {formatBytes(uploadedBytes)} / {formatBytes(totalBytes)} ({formatBytes(uploadSpeedBytesPerSec)}/s)
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all duration-150"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              {onCancelUpload && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={onCancelUpload}
                    className="text-xs font-medium text-rose-300 hover:text-rose-200"
                  >
                    Cancel upload
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {clientError && (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-500/35 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
          <span>{clientError}</span>
        </div>
      )}
    </div>
  );
}
