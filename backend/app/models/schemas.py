from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


MomentCategory = Literal[
    "interesting",
    "funny",
    "important",
    "motivational",
    "educational",
    "engaging",
]

AspectRatio = Literal["9:16", "16:9", "1:1"]
ExportQuality = Literal["720p", "1080p"]
SubtitlePreset = Literal["bold_pop", "minimal_clean", "neon_box", "classic_cinema"]
SubtitlePosition = Literal["bottom", "center", "top"]
VideoStatus = Literal["uploaded", "queued", "processing", "completed", "failed", "cancelled"]
PipelineStepState = Literal["pending", "running", "completed", "failed", "cancelled"]


class SubtitleStyle(BaseModel):
    preset: SubtitlePreset = "bold_pop"
    text_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#A855F7", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(default="#0B0F19", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_opacity: float = Field(default=0.72, ge=0.0, le=1.0)
    outline_color: str = Field(default="#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_size: int = Field(default=34, ge=18, le=64)
    position: SubtitlePosition = "bottom"
    uppercase: bool = False


class SubtitleCue(BaseModel):
    id: str
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    text: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_bounds(self) -> "SubtitleCue":
        if self.end <= self.start:
            raise ValueError("Subtitle cue end time must be greater than start time")
        return self


class TranscriptWord(BaseModel):
    word: str
    start: float
    end: float
    probability: float = 1.0


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[TranscriptWord] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    nlp_score: float = Field(ge=0.0, le=100.0)
    audio_score: float = Field(ge=0.0, le=100.0)
    visual_score: float = Field(ge=0.0, le=100.0)
    hook_score: float = Field(ge=0.0, le=100.0)
    completeness_score: float = Field(ge=0.0, le=100.0)


class PipelineStep(BaseModel):
    key: str
    label: str
    status: PipelineStepState = "pending"
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    detail: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RenderedVariant(BaseModel):
    quality: ExportQuality
    aspect_ratio: AspectRatio
    file_name: str
    file_size_bytes: int
    rendered_at: datetime
    signature: str


class ClipOut(BaseModel):
    id: str
    video_id: str
    index: int
    title: str
    category: MomentCategory
    secondary_categories: list[MomentCategory] = Field(default_factory=list)
    engagement_score: float = Field(ge=0.0, le=100.0)
    score_breakdown: ScoreBreakdown
    ai_reason: str
    transcript_text: str
    original_start: float
    original_end: float
    trim_start: float
    trim_end: float
    duration: float
    aspect_ratio: AspectRatio = "9:16"
    captions_enabled: bool = True
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)
    subtitles: list[SubtitleCue] = Field(default_factory=list)
    rendered_variants: dict[str, RenderedVariant] = Field(default_factory=dict)
    thumbnail_url: str
    preview_url: str
    created_at: datetime
    updated_at: datetime


class ClipUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=140)
    trim_start: float | None = Field(default=None, ge=0.0)
    trim_end: float | None = Field(default=None, gt=0.0)
    aspect_ratio: AspectRatio | None = None
    captions_enabled: bool | None = None
    subtitle_style: SubtitleStyle | None = None
    subtitles: list[SubtitleCue] | None = None


class RenderRequestIn(BaseModel):
    quality: ExportQuality = "1080p"
    aspect_ratio: AspectRatio | None = None
    force: bool = False


class BatchExportIn(BaseModel):
    quality: ExportQuality = "1080p"
    clip_ids: list[str] | None = None


class ExportRecordOut(BaseModel):
    id: str
    video_id: str
    kind: Literal["single", "zip"]
    quality: ExportQuality
    file_name: str
    file_size_bytes: int
    clip_count: int
    download_url: str
    created_at: datetime


class AnalysisSummary(BaseModel):
    language: str = "en"
    word_count: int = 0
    segment_count: int = 0
    scene_count: int = 0
    avg_audio_energy: float = 0.0
    peak_audio_moments: int = 0
    candidate_windows_evaluated: int = 0
    shorts_generated: int = 0


class VideoProjectOut(BaseModel):
    id: str
    title: str
    original_filename: str
    format_ext: str
    size_bytes: int
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    source_type: Literal["upload", "youtube"] = "upload"
    youtube_url: str | None = None
    status: VideoStatus
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    current_stage: str = "uploaded"
    error_message: str | None = None
    target_shorts_count: int = 10
    default_aspect_ratio: AspectRatio = "9:16"
    default_quality: ExportQuality = "1080p"
    pipeline_steps: list[PipelineStep] = Field(default_factory=list)
    analysis_summary: AnalysisSummary = Field(default_factory=AnalysisSummary)
    poster_url: str
    source_url: str
    clips_count: int = 0
    created_at: datetime
    updated_at: datetime


class YouTubePreviewIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class YouTubePreviewOut(BaseModel):
    url: str
    video_key: str
    title: str
    channel: str
    duration: float
    thumbnail_url: str | None = None
    valid_duration: bool
    validation_message: str | None = None


class YouTubeImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    title: str | None = Field(default=None, max_length=120)
    target_shorts_count: int = Field(default=10, ge=5, le=15)
    default_aspect_ratio: AspectRatio = "9:16"
    default_quality: ExportQuality = "1080p"
    auto_process: bool = True


class UserRegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=6, max_length=128)


class UserLoginIn(BaseModel):
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime


class AuthTokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


class SystemHealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    mongodb_connected: bool
    ffmpeg_available: bool
    ffprobe_available: bool
    faster_whisper_available: bool
    scenedetect_available: bool
    opencv_available: bool
    nlp_model_available: bool
    yt_dlp_available: bool = False
    min_video_duration_seconds: float
    max_video_duration_seconds: float
