import { Link } from "react-router-dom";
import {
  ArrowRight,
  Cpu,
  Download,
  Film,
  Layers,
  LogIn,
  Mic,
  Scissors,
  Sparkles,
  UploadCloud,
  Wand2,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const WORKFLOW_STEPS = [
  { step: "01", title: "Upload File or YouTube Link", desc: "Drag & drop MP4/MOV/MKV/WebM or paste any YouTube video under 20 min." },
  { step: "02", title: "Extract & Transcribe", desc: "FFmpeg extracts audio; Faster-Whisper transcribes word timings." },
  { step: "03", title: "Detect Scenes & Energy", desc: "PySceneDetect, OpenCV & acoustic analysis score visual/audio peaks." },
  { step: "04", title: "NLP Moment Ranking", desc: "Transformer embeddings identify funny, educational, motivational & key clips." },
  { step: "05", title: "Edit & Burn Captions", desc: "Trim bounds, style captions, switch 9:16 / 16:9 / 1:1 aspect ratios." },
  { step: "06", title: "Export HD MP4 & ZIP", desc: "Render crisp 720p / 1080p MP4 shorts individually or as one ZIP." },
];

export function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[#07090f] text-slate-100">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#07090f]/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-600/25">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight text-white">Clipora AI</span>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <Link
                to="/dashboard"
                className="rounded-xl px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/5 hover:text-white"
              >
                Dashboard
              </Link>
            ) : (
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/5 hover:text-white"
              >
                <LogIn className="h-4 w-4" />
                Sign In
              </Link>
            )}
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-violet-600/25 hover:from-violet-500 hover:to-indigo-500"
            >
              <UploadCloud className="h-4 w-4" />
              Create Shorts
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-20 sm:py-28">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(124,58,237,0.22),_transparent_55%)]" />
        <div className="relative mx-auto max-w-5xl px-4 text-center sm:px-6">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-medium text-violet-200">
            <Cpu className="h-3.5 w-3.5 text-cyan-400" />
            Faster-Whisper • PySceneDetect • SentenceTransformers • FFmpeg
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl leading-[1.1]">
            Turn Long Videos into{" "}
            <span className="bg-gradient-to-r from-violet-400 via-fuchsia-300 to-cyan-300 bg-clip-text text-transparent">
              High-Engagement AI Shorts
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base text-slate-400 sm:text-lg">
            Upload podcasts, tutorials, interviews, or streams up to 20 minutes long. Clipora AI transcribes every word, detects scene changes and vocal excitement, ranks the best 5–15 non-overlapping 10–20s moments, and renders styled HD MP4 shorts.
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/upload"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 px-6 py-3.5 text-sm font-semibold text-white shadow-xl shadow-violet-600/25 hover:opacity-95 transition-opacity"
            >
              Upload Video (Up to 20 Min)
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-semibold text-slate-200 hover:bg-white/10"
            >
              Open Studio Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* Capabilities Grid */}
      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="grid gap-5 md:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-6">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-violet-500/15 text-violet-300">
              <Mic className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">Multimodal AI Discovery</h3>
            <p className="mt-2 text-sm text-slate-400">
              Combines Faster-Whisper word-level speech transcription, PySceneDetect shot boundaries, OpenCV speaker tracking, spectral audio excitement, and semantic NLP scoring.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-6">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-300">
              <Wand2 className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">Interactive Shorts Editor</h3>
            <p className="mt-2 text-sm text-slate-400">
              Fine-tune start/end clip trims, edit auto-generated captions cue by cue, customize subtitle presets, colors, and sizes, and switch between 9:16, 16:9, or 1:1 framing.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#0d121f] p-6">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300">
              <Download className="h-5 w-5" />
            </div>
            <h3 className="text-base font-semibold text-white">True HD FFmpeg Exports</h3>
            <p className="mt-2 text-sm text-slate-400">
              Render broadcast-grade 720p and 1080p MP4 shorts with burned-in styled ASS subtitles, face-centered crops, and one-click batch ZIP downloads.
            </p>
          </div>
        </div>
      </section>

      {/* Workflow Section */}
      <section className="border-t border-white/10 bg-[#0a0e18] py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold text-white sm:text-3xl">End-to-End Real AI Pipeline</h2>
              <p className="mt-2 text-sm text-slate-400">
                Every stage runs real local ML & FFmpeg processing with live progress tracking in MongoDB.
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1.5"><Scissors className="h-4 w-4 text-violet-400" /> 5–15 Shorts</span>
              <span className="flex items-center gap-1.5"><Film className="h-4 w-4 text-cyan-400" /> 10–20s Clips</span>
              <span className="flex items-center gap-1.5"><Layers className="h-4 w-4 text-emerald-400" /> Zero Duplicates</span>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {WORKFLOW_STEPS.map((item) => (
              <div key={item.step} className="rounded-2xl border border-white/10 bg-[#0f1524] p-5">
                <span className="font-mono text-xs font-bold text-violet-400">STEP {item.step}</span>
                <h3 className="mt-2 text-base font-semibold text-white">{item.title}</h3>
                <p className="mt-1.5 text-sm text-slate-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
