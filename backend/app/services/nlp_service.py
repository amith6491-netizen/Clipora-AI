from dataclasses import dataclass
import math
import re
from threading import Lock

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import Settings
from app.models.schemas import MomentCategory

CATEGORY_PROTOTYPES: dict[MomentCategory, list[str]] = {
    "interesting": [
        "surprising fact counterintuitive insight mind blowing revelation unexpected discovery",
        "did you know here is the weird part nobody realizes why this actually happens",
        "fascinating story secret behind how things turned out completely differently",
    ],
    "funny": [
        "hilarious joke comedy funny story laughing witty banter ridiculous mistake",
        "so embarrassing couldn't stop laughing sarcasm punchline comedy moment",
        "absurd situation humorous reaction playful teasing funny misunderstanding",
    ],
    "important": [
        "critical decision main takeaway key conclusion serious warning essential point",
        "most important thing to remember strategic impact major announcement",
        "fundamental argument core thesis real world consequences big picture",
    ],
    "motivational": [
        "never give up overcome failure build discipline mindset shift achieve your goals",
        "inspiring lesson hard work resilience courage confidence believe in yourself",
        "how to keep going when everything feels impossible stay consistent and win",
    ],
    "educational": [
        "step by step explanation how it works clear tutorial practical framework lesson",
        "let me break down the concept definition three principles to understand",
        "science engineering history coding method example showing why it works",
    ],
    "engaging": [
        "wait until you hear what happened next dramatic turning point unforgettable moment",
        "imagine this scenario big question everyone asks captivating story hook",
        "bold claim honest truth relatable struggle gripping conversation highlight",
    ],
}

HOOK_PATTERNS = [
    r"\b(here'?s why|here is why|the secret|nobody tells you|truth is|wait until|stop doing)\b",
    r"\b(three|3|five|5|two|2|top|biggest|best|worst)\s+(things|reasons|mistakes|ways|lessons|rules|secrets)\b",
    r"\b(why do|how do|how to|what if|have you ever|did you know|imagine)\b",
    r"\b(but actually|however|turned out|plot twist|the problem is|the crazy part)\b",
]

HUMOR_LEXICON = {
    "funny", "laugh", "laughing", "hilarious", "joke", "kidding", "ridiculous",
    "absurd", "awkward", "embarrassing", "sarcasm", "comedy", "crazy", "insane",
    "haha", "lol", "wait what", "no way", "bro",
}

MOTIVATION_LEXICON = {
    "achieve", "success", "discipline", "mindset", "courage", "consistency", "overcome",
    "failure", "believe", "focus", "growth", "purpose", "dream", "strength", "resilience",
    "start today", "keep going", "never quit", "improve", "confidence",
}

EDUCATION_LEXICON = {
    "because", "example", "means", "works", "step", "principle", "method", "framework",
    "reason", "algorithm", "process", "explain", "definition", "research", "study",
    "percent", "data", "first", "second", "third", "learn", "understand",
}

IMPORTANT_LEXICON = {
    "critical", "essential", "important", "key", "conclusion", "takeaway", "decision",
    "impact", "strategy", "future", "risk", "problem", "solution", "priority", "matter",
    "fundamental", "warning", "remember", "ultimately",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "so", "yet", "for", "nor", "of", "on", "in",
    "to", "at", "by", "from", "with", "about", "as", "into", "like", "through", "after", "over",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "can", "may", "might", "must", "that", "this",
    "these", "those", "it", "its", "it's", "i", "you", "we", "they", "he", "she", "me", "my",
    "your", "our", "their", "just", "really", "very", "actually", "basically", "literally",
    "um", "uh", "well", "yeah", "right", "okay", "ok", "know", "mean", "think", "going", "got",
}


@dataclass
class NlpWindowEvaluation:
    nlp_score: float
    hook_score: float
    primary_category: MomentCategory
    secondary_categories: list[MomentCategory]
    category_scores: dict[MomentCategory, float]
    title: str
    embedding: np.ndarray | None


_embedder_cache: dict[str, object] = {}
_embedder_lock = Lock()
_vader = SentimentIntensityAnalyzer()


def get_sentence_embedder(model_name: str):
    """Load and cache the SentenceTransformer model with local-cache fallback."""
    from sentence_transformers import SentenceTransformer

    with _embedder_lock:
        if model_name not in _embedder_cache:
            try:
                _embedder_cache[model_name] = SentenceTransformer(model_name, local_files_only=True)
            except Exception:
                _embedder_cache[model_name] = SentenceTransformer(model_name)
        return _embedder_cache[model_name]


def _count_lexicon_hits(text_lower: str, words_set: set[str], lexicon: set[str]) -> int:
    hits = 0
    for term in lexicon:
        if " " in term:
            if term in text_lower:
                hits += 1
        elif term in words_set:
            hits += 1
    return hits


def _compute_hook_score(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    opening = sentences[0] if sentences else text[:120]
    opening_lower = opening.lower()

    score = 32.0
    if "?" in opening:
        score += 24.0
    elif "?" in text:
        score += 10.0

    pattern_hits = sum(1 for pat in HOOK_PATTERNS if re.search(pat, text.lower()))
    score += min(28.0, pattern_hits * 14.0)

    if re.search(r"\b\d+\b", opening):
        score += 10.0

    vader_open = _vader.polarity_scores(opening)
    score += min(18.0, abs(vader_open["compound"]) * 22.0)

    if "!" in opening:
        score += 6.0

    word_count = len(opening.split())
    if 4 <= word_count <= 16:
        score += 8.0

    return round(min(100.0, max(10.0, score)), 2)


def generate_clip_title(text: str, category: MomentCategory, top_terms: list[str]) -> str:
    """Create a concise, context-preserving headline directly from the clip transcript."""
    cleaned = re.sub(r"\b(um+|uh+|you know|i mean|sort of|kind of)\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.strip().split()) >= 4]

    # Prefer a sharp opening question or punchy sentence if it fits cleanly
    chosen: str | None = None
    for s in sentences:
        words = s.split()
        if "?" in s and 4 <= len(words) <= 11:
            chosen = s
            break
    if chosen is None and sentences:
        # Pick the sentence containing the highest count of salient topic keywords
        top_set = {t.lower() for t in top_terms}
        chosen = max(
            sentences,
            key=lambda s: sum(1 for w in re.findall(r"[a-zA-Z]+", s.lower()) if w in top_set)
            + (1.5 if "?" in s or "!" in s else 0.0),
        )

    if chosen:
        words = chosen.rstrip(".").split()
        if len(words) > 10:
            # Trim leading filler clause if comma-separated
            parts = [p.strip() for p in re.split(r"[,;:]", chosen) if len(p.strip().split()) >= 4]
            if parts:
                best_part = max(parts, key=lambda p: len(p.split()) if len(p.split()) <= 10 else 0)
                words = best_part.split()
        words = words[:9]
        raw_title = " ".join(words).strip(" ,;:-")
        if raw_title:
            # Smart title casing keeping short articles/prepositions lowercase except first word
            formatted = []
            for idx, w in enumerate(raw_title.split()):
                if idx > 0 and w.lower() in {"a", "an", "the", "and", "or", "of", "in", "on", "to", "for", "with"}:
                    formatted.append(w.lower())
                elif w.isupper() and len(w) > 1:
                    formatted.append(w)
                else:
                    formatted.append(w[0].upper() + w[1:])
            title = " ".join(formatted)
            if len(title) >= 8:
                return title[:120]

    if top_terms:
        joined = " ".join(t.capitalize() for t in top_terms[:4])
        prefix = {
            "interesting": "Insight on",
            "funny": "Funny Moment:",
            "important": "Key Point:",
            "motivational": "Mindset Shift:",
            "educational": "How to Master",
            "engaging": "Highlight:",
        }[category]
        return f"{prefix} {joined}"[:120]

    return f"{category.capitalize()} Moment Highlight"


def evaluate_candidates_nlp(
    candidate_texts: list[str],
    full_transcript_text: str,
    settings: Settings,
) -> list[NlpWindowEvaluation]:
    """Evaluate candidate clip transcripts using SentenceTransformers, TF-IDF centrality, and VADER."""
    if not candidate_texts:
        return []

    # 1. TF-IDF topic centrality over all candidates
    vectorizer = TfidfVectorizer(stop_words="english", max_features=400, ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform([full_transcript_text, *candidate_texts])
        feature_names = vectorizer.get_feature_names_out()
        doc_vec = tfidf_matrix[0].toarray()[0]
        cand_vecs = tfidf_matrix[1:].toarray()
    except ValueError:
        feature_names = np.array([])
        doc_vec = np.array([])
        cand_vecs = np.zeros((len(candidate_texts), 1))

    # 2. Transformer semantic embeddings (real SentenceTransformer model)
    embedder = get_sentence_embedder(settings.nlp_embedding_model)
    cand_embeddings = embedder.encode(candidate_texts, normalize_embeddings=True, show_progress_bar=False)

    proto_categories: list[MomentCategory] = list(CATEGORY_PROTOTYPES.keys())
    proto_texts: list[str] = []
    proto_owners: list[MomentCategory] = []
    for cat, anchors in CATEGORY_PROTOTYPES.items():
        for anchor in anchors:
            proto_texts.append(anchor)
            proto_owners.append(cat)

    proto_embeddings = embedder.encode(proto_texts, normalize_embeddings=True, show_progress_bar=False)
    sim_matrix = np.matmul(cand_embeddings, proto_embeddings.T)  # shape: (N_cand, N_proto)

    evaluations: list[NlpWindowEvaluation] = []
    for idx, text in enumerate(candidate_texts):
        tokens = re.findall(r"[a-zA-Z0-9']+", text.lower())
        words_set = set(tokens)
        content_words = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
        lexical_diversity = len(set(content_words)) / max(1, len(content_words))
        info_density = len(content_words) / max(1, len(tokens))

        # Semantic similarity per category (max + mean over anchors)
        cat_scores: dict[MomentCategory, float] = {}
        for cat in proto_categories:
            cols = [c_i for c_i, owner in enumerate(proto_owners) if owner == cat]
            sims = sim_matrix[idx, cols]
            semantic_val = float(0.65 * np.max(sims) + 0.35 * np.mean(sims))
            # Cosine similarity on MiniLM usually lies in [0.05, 0.55] for topic match
            base_cat = min(100.0, max(5.0, (semantic_val + 0.08) * 155.0))
            cat_scores[cat] = base_cat

        text_lower = text.lower()
        sentiment = _vader.polarity_scores(text)
        compound_abs = abs(sentiment["compound"])

        # Add genuine lexical & sentiment signals per category
        humor_hits = _count_lexicon_hits(text_lower, words_set, HUMOR_LEXICON)
        motiv_hits = _count_lexicon_hits(text_lower, words_set, MOTIVATION_LEXICON)
        edu_hits = _count_lexicon_hits(text_lower, words_set, EDUCATION_LEXICON)
        imp_hits = _count_lexicon_hits(text_lower, words_set, IMPORTANT_LEXICON)

        # Sentiment shift inside the window (arc between first and second half)
        mid = max(1, len(text) // 2)
        arc_delta = abs(
            _vader.polarity_scores(text[:mid])["compound"]
            - _vader.polarity_scores(text[mid:])["compound"]
        )

        # Topic centrality from TF-IDF cosine with full transcript
        if doc_vec.size > 0 and cand_vecs.shape[1] == doc_vec.size:
            c_vec = cand_vecs[idx]
            denom = (np.linalg.norm(doc_vec) * np.linalg.norm(c_vec)) + 1e-8
            centrality = float(np.dot(doc_vec, c_vec) / denom)
            top_indices = np.argsort(c_vec)[::-1][:6]
            top_terms = [str(feature_names[ti]) for ti in top_indices if c_vec[ti] > 0]
        else:
            centrality = 0.2
            top_terms = content_words[:5]

        hook_score = _compute_hook_score(text)

        cat_scores["funny"] = min(100.0, cat_scores["funny"] + humor_hits * 9.5 + max(0.0, sentiment["pos"] * 18.0))
        cat_scores["motivational"] = min(100.0, cat_scores["motivational"] + motiv_hits * 8.5 + max(0.0, sentiment["compound"] * 15.0))
        cat_scores["educational"] = min(100.0, cat_scores["educational"] + edu_hits * 7.5 + info_density * 14.0)
        cat_scores["important"] = min(100.0, cat_scores["important"] + imp_hits * 8.5 + centrality * 25.0)
        cat_scores["interesting"] = min(100.0, cat_scores["interesting"] + lexical_diversity * 14.0 + (12.0 if "?" in text else 0.0))
        cat_scores["engaging"] = min(100.0, cat_scores["engaging"] + arc_delta * 18.0 + compound_abs * 14.0 + hook_score * 0.16)

        sorted_cats = sorted(cat_scores.items(), key=lambda item: item[1], reverse=True)
        primary_category = sorted_cats[0][0]
        secondary_categories = [c for c, s in sorted_cats[1:3] if s >= sorted_cats[0][1] - 12.0]

        # Overall NLP richness score combining top category strength, centrality, sentiment arc & density
        top_cat_val = sorted_cats[0][1]
        nlp_raw = (
            0.48 * top_cat_val
            + 0.20 * min(100.0, centrality * 135.0)
            + 0.16 * min(100.0, (compound_abs * 55.0 + arc_delta * 45.0))
            + 0.16 * min(100.0, (lexical_diversity * 65.0 + info_density * 55.0))
        )
        # Subtle penalty if too sparse (< 16 words)
        word_count = len(tokens)
        if word_count < 16:
            nlp_raw *= max(0.45, word_count / 16.0)
        elif word_count > 85:
            nlp_raw *= math.exp(-0.004 * (word_count - 85))

        nlp_score = round(min(100.0, max(8.0, nlp_raw)), 2)
        title = generate_clip_title(text, primary_category, top_terms)

        evaluations.append(
            NlpWindowEvaluation(
                nlp_score=nlp_score,
                hook_score=hook_score,
                primary_category=primary_category,
                secondary_categories=secondary_categories,
                category_scores={k: round(v, 2) for k, v in cat_scores.items()},
                title=title,
                embedding=cand_embeddings[idx],
            )
        )

    return evaluations
