export type MomentCategory =
  | "interesting"
  | "funny"
  | "important"
  | "motivational"
  | "educational"
  | "engaging";

export type AspectRatio = "9:16" | "16:9" | "1:1";
export type ExportQuality = "720p" | "1080p";
export type SubtitlePreset = "bold_pop" | "minimal_clean" | "neon_box" | "classic_cinema";
export type SubtitlePosition = "bottom" | "center" | "top";
export type VideoStatus = "uploaded" | "queued" | "processing" | "completed" | "failed" | "cancelled";
export type PipelineStepState = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface SubtitleStyle {
  preset: SubtitlePreset;
  text_color: string;
  accent_color: string;
  background_color: string;
  background_opacity: number;
  outline_color: string;
  font_size: number;
  position: SubtitlePosition;
  uppercase: boolean;
}

export interface SubtitleCue {
  id: string;
  start: number;
  end: number;
  text: string;
}

export interface ScoreBreakdown {
  nlp_score: number;
  audio_score: number;
  visual_score: number;
  hook_score: number;
  completeness_score: number;
}

export interface RenderedVariant {
  quality: ExportQuality;
  aspect_ratio: AspectRatio;
  file_name: string;
  file_size_bytes: number;
  rendered_at: string;
  signature: string;
}

export interface Clip {
  id: string;
  video_id: string;
  index: number;
  title: string;
  category: MomentCategory;
  secondary_categories: MomentCategory[];
  engagement_score: number;
  score_breakdown: ScoreBreakdown;
  ai_reason: string;
  transcript_text: string;
  original_start: number;
  original_end: number;
  trim_start: number;
  trim_end: number;
  duration: number;
  aspect_ratio: AspectRatio;
  captions_enabled: boolean;
  subtitle_style: SubtitleStyle;
  subtitles: SubtitleCue[];
  rendered_variants: Record<string, RenderedVariant>;
  thumbnail_url: string;
  preview_url: string;
  created_at: string;
  updated_at: string;
}

export interface ClipUpdatePayload {
  title?: string;
  trim_start?: number;
  trim_end?: number;
  aspect_ratio?: AspectRatio;
  captions_enabled?: boolean;
  subtitle_style?: SubtitleStyle;
  subtitles?: SubtitleCue[];
}

export interface PipelineStep {
  key: string;
  label: string;
  status: PipelineStepState;
  progress: number;
  detail: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AnalysisSummary {
  language: string;
  word_count: number;
  segment_count: number;
  scene_count: number;
  avg_audio_energy: number;
  peak_audio_moments: number;
  candidate_windows_evaluated: number;
  shorts_generated: number;
}

export interface VideoProject {
  id: string;
  title: string;
  original_filename: string;
  format_ext: string;
  size_bytes: number;
  duration: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  source_type: "upload" | "youtube" | "instagram";
  youtube_url?: string | null;
  instagram_url?: string | null;
  status: VideoStatus;
  progress: number;
  current_stage: string;
  error_message: string | null;
  target_shorts_count: number;
  default_aspect_ratio: AspectRatio;
  default_quality: ExportQuality;
  pipeline_steps: PipelineStep[];
  analysis_summary: AnalysisSummary;
  poster_url: string;
  source_url: string;
  clips_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExportRecord {
  id: string;
  video_id: string;
  kind: "single" | "zip";
  quality: ExportQuality;
  file_name: string;
  file_size_bytes: number;
  clip_count: number;
  download_url: string;
  created_at: string;
}

export interface SystemHealth {
  status: "ok" | "degraded";
  mongodb_connected: boolean;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  faster_whisper_available: boolean;
  scenedetect_available: boolean;
  opencv_available: boolean;
  nlp_model_available: boolean;
  yt_dlp_available: boolean;
  min_video_duration_seconds: number;
  max_video_duration_seconds: number;
}

export interface YouTubePreview {
  url: string;
  video_key: string;
  title: string;
  channel: string;
  duration: number;
  thumbnail_url: string | null;
  valid_duration: boolean;
  validation_message: string | null;
}

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface InstagramDownload {
  id: string;
  url: string;
  shortcode: string;
  title: string;
  author: string;
  duration: number;
  width: number;
  height: number;
  file_name: string;
  file_size_bytes: number;
  preview_url: string;
  download_url: string;
  thumbnail_url: string;
  video_id?: string | null;
  clip_id?: string | null;
  edit_url?: string | null;
  created_at: string;
}

export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
}

export interface TranscriptPayload {
  video_id: string;
  language: string;
  segments: TranscriptSegment[];
  scenes: { start: number; end: number }[];
}

export interface ProgressEventPayload {
  video_id: string;
  status: VideoStatus;
  progress: number;
  current_stage: string;
  detail?: string;
  pipeline_steps: PipelineStep[];
  error_message?: string | null;
}
