from dataclasses import dataclass
import re

import numpy as np

from app.core.config import Settings
from app.models.schemas import MomentCategory, ScoreBreakdown, TranscriptSegment, TranscriptWord
from app.services.audio_service import AudioEnergyProfile, score_audio_window
from app.services.nlp_service import NlpWindowEvaluation, evaluate_candidates_nlp
from app.services.scene_service import VisualTimelineProfile, score_visual_window


@dataclass
class SentenceUnit:
    start: float
    end: float
    text: str
    starts_sentence: bool
    ends_sentence: bool


@dataclass
class RankedClipCandidate:
    start: float
    end: float
    duration: float
    text: str
    title: str
    category: MomentCategory
    secondary_categories: list[MomentCategory]
    engagement_score: float
    score_breakdown: ScoreBreakdown
    ai_reason: str
    preferred_crop_x_ratio: float
    scene_cuts: int
    audio_peaks: int
    embedding: np.ndarray | None


def _flatten_words(segments: list[TranscriptSegment]) -> list[TranscriptWord]:
    words: list[TranscriptWord] = []
    for seg in segments:
        if seg.words:
            words.extend(seg.words)
        else:
            tokens = seg.text.split()
            if not tokens:
                continue
            step = max(0.05, (seg.end - seg.start) / len(tokens))
            for idx, tok in enumerate(tokens):
                ws = seg.start + idx * step
                words.append(TranscriptWord(word=tok, start=round(ws, 3), end=round(ws + step, 3)))
    words.sort(key=lambda w: w.start)
    return words


def _build_sentence_units(segments: list[TranscriptSegment]) -> list[SentenceUnit]:
    """Group Whisper words into complete sentences or natural clause chunks."""
    words = _flatten_words(segments)
    if not words:
        return []

    units: list[SentenceUnit] = []
    buf: list[TranscriptWord] = []
    current_starts_sentence = True

    def flush(ends_sentence: bool) -> None:
        nonlocal current_starts_sentence
        if not buf:
            return
        text = " ".join(w.word for w in buf).strip()
        if text:
            units.append(
                SentenceUnit(
                    start=buf[0].start,
                    end=buf[-1].end,
                    text=text,
                    starts_sentence=current_starts_sentence,
                    ends_sentence=ends_sentence,
                )
            )
        buf.clear()
        current_starts_sentence = ends_sentence

    for idx, w in enumerate(words):
        buf.append(w)
        next_gap = (words[idx + 1].start - w.end) if idx + 1 < len(words) else 1.0
        span = w.end - buf[0].start
        terminal_punct = w.word.endswith((".", "?", "!"))
        clause_punct = w.word.endswith((",", ";", ":"))

        if terminal_punct or next_gap >= 0.75:
            flush(ends_sentence=True)
        elif span >= 14.0 and (clause_punct or next_gap >= 0.28):
            flush(ends_sentence=False)
        elif span >= 18.5:
            flush(ends_sentence=False)

    flush(ends_sentence=True)
    return units


def _align_boundary_to_scene(
    target_t: float,
    min_limit: float,
    max_limit: float,
    cut_timestamps: list[float],
    tolerance: float = 0.5,
) -> float:
    best = target_t
    best_dist = tolerance + 1.0
    for cut in cut_timestamps:
        dist = abs(cut - target_t)
        if dist <= tolerance and min_limit <= cut <= max_limit and dist < best_dist:
            best = cut
            best_dist = dist
    return round(best, 3)


def _build_candidate_windows(
    segments: list[TranscriptSegment],
    video_duration: float,
    visual_profile: VisualTimelineProfile | None,
    min_clip: float,
    max_clip: float,
) -> list[tuple[float, float, str, float]]:
    """Return list of (start, end, text, completeness_score)."""
    units = _build_sentence_units(segments)
    cuts = visual_profile.cut_timestamps if visual_profile else []
    candidates: list[tuple[float, float, str, float]] = []
    seen_spans: set[tuple[int, int]] = set()

    if units:
        n = len(units)
        for i in range(n):
            acc_texts: list[str] = []
            for j in range(i, n):
                acc_texts.append(units[j].text)
                raw_start = units[i].start
                raw_end = units[j].end
                raw_dur = raw_end - raw_start

                if raw_dur > max_clip + 0.6:
                    break

                # Pad cleanly around speech while keeping within [min_clip, max_clip]
                if raw_dur < min_clip:
                    needed = min_clip - raw_dur
                    # Only pad short speech phrases up to 3.5s total padding so we don't capture huge silence
                    if needed > 3.5 and j + 1 < n:
                        continue
                    if needed <= 3.5:
                        left_pad = min(raw_start, needed * 0.35 + 0.2)
                        right_pad = min(video_duration - raw_end, needed - left_pad + 0.25)
                        start_t = max(0.0, raw_start - left_pad)
                        end_t = min(video_duration, raw_end + right_pad)
                        if end_t - start_t < min_clip:
                            end_t = min(video_duration, start_t + min_clip)
                        if end_t - start_t < min_clip:
                            start_t = max(0.0, end_t - min_clip)
                    else:
                        continue
                else:
                    start_t = max(0.0, raw_start - 0.2)
                    end_t = min(video_duration, raw_end + 0.3)
                    if end_t - start_t > max_clip:
                        end_t = start_t + max_clip

                dur = end_t - start_t
                if dur < min_clip - 0.05 or dur > max_clip + 0.05:
                    continue

                # Gentle scene-cut snap that preserves the spoken words inside [raw_start, raw_end]
                start_t = _align_boundary_to_scene(
                    start_t,
                    max(0.0, end_t - max_clip),
                    min(raw_start, end_t - min_clip),
                    cuts,
                    tolerance=0.45,
                )
                end_t = _align_boundary_to_scene(
                    end_t,
                    max(raw_end, start_t + min_clip),
                    min(video_duration, start_t + max_clip),
                    cuts,
                    tolerance=0.45,
                )

                span_key = (int(round(start_t * 2)), int(round(end_t * 2)))
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)

                completeness = 72.0
                if units[i].starts_sentence:
                    completeness += 14.0
                if units[j].ends_sentence:
                    completeness += 14.0

                candidates.append((round(start_t, 3), round(end_t, 3), " ".join(acc_texts).strip(), completeness))

    # Fallback coverage when video has sparse speech or uncovered timeline gaps
    if video_duration >= min_clip:
        covered_bins = [False] * max(1, int(video_duration) + 1)
        for s_t, e_t, _, _ in candidates:
            for sec in range(max(0, int(s_t)), min(len(covered_bins), int(e_t) + 1)):
                covered_bins[sec] = True

        uncovered_ratio = sum(1 for c in covered_bins if not c) / len(covered_bins)
        if len(candidates) < 12 or uncovered_ratio > 0.25:
            win_lengths = (min_clip, min(max_clip, max(min_clip + 2.0, 14.0)))
            step = max(4.0, min_clip * 0.5)
            t = 0.0
            while t + min_clip <= video_duration + 0.01:
                for win_len in win_lengths:
                    s = round(t, 3)
                    e = round(min(video_duration, s + win_len), 3)
                    if e - s < min_clip:
                        continue
                    # Only add fallback if this interval isn't already well-covered by speech candidates
                    mid_sec = min(len(covered_bins) - 1, max(0, int((s + e) * 0.5)))
                    if len(candidates) >= 12 and covered_bins[mid_sec]:
                        continue
                    span_key = (int(round(s * 2)), int(round(e * 2)))
                    if span_key in seen_spans:
                        continue
                    seen_spans.add(span_key)
                    nearby_text = " ".join(seg.text for seg in segments if seg.end >= s and seg.start <= e).strip()
                    if not nearby_text:
                        nearby_text = f"Visual highlight sequence from {s:.0f}s to {e:.0f}s."
                    candidates.append((s, e, nearby_text, 65.0))
                t += step

    return candidates


def _token_jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-zA-Z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-zA-Z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def select_and_rank_shorts(
    segments: list[TranscriptSegment],
    audio_profile: AudioEnergyProfile | None,
    visual_profile: VisualTimelineProfile | None,
    video_duration: float,
    target_shorts_count: int,
    settings: Settings,
) -> tuple[list[RankedClipCandidate], int]:
    """Generate 5-15 non-overlapping 10-20s ranked clips with multimodal scoring & deduplication."""
    min_clip = settings.min_clip_duration_seconds
    max_clip = settings.max_clip_duration_seconds

    raw_windows = _build_candidate_windows(
        segments=segments,
        video_duration=video_duration,
        visual_profile=visual_profile,
        min_clip=min_clip,
        max_clip=max_clip,
    )
    if not raw_windows:
        return [], 0

    full_text = " ".join(seg.text for seg in segments).strip() or "Video highlight transcript"
    nlp_evals = evaluate_candidates_nlp(
        candidate_texts=[w[2] for w in raw_windows],
        full_transcript_text=full_text,
        settings=settings,
    )

    scored: list[RankedClipCandidate] = []
    for (start_t, end_t, text, completeness), nlp_ev in zip(raw_windows, nlp_evals):
        audio_score, speech_ratio, audio_peaks = score_audio_window(audio_profile, start_t, end_t)
        visual_score, scene_cuts, crop_x = score_visual_window(visual_profile, start_t, end_t)

        # Penalize largely silent gaps in audio if speech was sparse
        effective_audio = audio_score * (0.75 + 0.25 * speech_ratio)
        engagement = (
            0.42 * nlp_ev.nlp_score
            + 0.22 * effective_audio
            + 0.14 * visual_score
            + 0.14 * nlp_ev.hook_score
            + 0.08 * completeness
        )
        engagement = round(min(98.5, max(18.0, engagement)), 1)

        reasons: list[str] = [f"Strong {nlp_ev.primary_category} signal ({nlp_ev.category_scores[nlp_ev.primary_category]:.0f}/100)"]
        if nlp_ev.hook_score >= 65:
            reasons.append("compelling opening hook")
        if audio_peaks > 0 or audio_score >= 65:
            reasons.append(f"elevated vocal energy ({audio_score:.0f}/100)")
        if scene_cuts > 0:
            reasons.append(f"{scene_cuts} dynamic scene transition{'s' if scene_cuts > 1 else ''}")
        if completeness >= 95:
            reasons.append("complete sentence arc")

        scored.append(
            RankedClipCandidate(
                start=start_t,
                end=end_t,
                duration=round(end_t - start_t, 3),
                text=text,
                title=nlp_ev.title,
                category=nlp_ev.primary_category,
                secondary_categories=nlp_ev.secondary_categories,
                engagement_score=engagement,
                score_breakdown=ScoreBreakdown(
                    nlp_score=nlp_ev.nlp_score,
                    audio_score=round(effective_audio, 2),
                    visual_score=visual_score,
                    hook_score=nlp_ev.hook_score,
                    completeness_score=round(completeness, 2),
                ),
                ai_reason="; ".join(reasons).capitalize() + ".",
                preferred_crop_x_ratio=crop_x,
                scene_cuts=scene_cuts,
                audio_peaks=audio_peaks,
                embedding=nlp_ev.embedding,
            )
        )

    # Greedy NMS with temporal non-overlap & semantic deduplication + gentle category diversity
    desired = max(settings.min_shorts_count, min(settings.max_shorts_count, target_shorts_count))
    pool = sorted(scored, key=lambda c: c.engagement_score, reverse=True)
    selected: list[RankedClipCandidate] = []
    category_counts: dict[MomentCategory, int] = {}

    def _conflicts_with_selected(cand: RankedClipCandidate, min_gap: float) -> bool:
        for chosen in selected:
            if not (cand.end + min_gap <= chosen.start or cand.start >= chosen.end + min_gap):
                return True
            if cand.embedding is not None and chosen.embedding is not None:
                cos_sim = float(np.dot(cand.embedding, chosen.embedding))
                if cos_sim >= 0.78:
                    return True
            if _token_jaccard(cand.text, chosen.text) >= 0.60:
                return True
        return False

    # Pass 1: strict non-overlap with >= 2.0s gap and category diversity bonus
    remaining = list(pool)
    while len(selected) < desired and remaining:
        best_idx = -1
        best_adj = -1.0
        for idx, cand in enumerate(remaining):
            if _conflicts_with_selected(cand, min_gap=2.0):
                continue
            cat_seen = category_counts.get(cand.category, 0)
            diversity_bonus = 3.5 if cat_seen == 0 else (-1.5 * max(0, cat_seen - 2))
            adj = cand.engagement_score + diversity_bonus
            if adj > best_adj:
                best_adj = adj
                best_idx = idx
        if best_idx < 0:
            break
        chosen = remaining.pop(best_idx)
        selected.append(chosen)
        category_counts[chosen.category] = category_counts.get(chosen.category, 0) + 1

    # Pass 2: if fewer than min_shorts_count, relax temporal gap to 0.0s (still zero overlap!)
    if len(selected) < settings.min_shorts_count:
        for cand in pool:
            if len(selected) >= settings.min_shorts_count:
                break
            if cand in selected:
                continue
            overlap = any(not (cand.end <= s.start or cand.start >= s.end) for s in selected)
            if not overlap:
                selected.append(cand)

    selected.sort(key=lambda c: c.engagement_score, reverse=True)
    return selected[: settings.max_shorts_count], len(raw_windows)
