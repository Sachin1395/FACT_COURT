import re
from difflib import SequenceMatcher


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Maximum number of candidate pairs sent to relationship adjudication.
MAX_CANDIDATES = 150

# Minimum score required for a pair to be considered plausible at all.
MIN_CANDIDATE_SCORE = 18.0


# ---------------------------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------------------------

def _normalize_text(value):
    if not value:
        return ""

    value = str(value).lower().strip()

    # Preserve numbers, letters, percentage signs, and spaces.
    value = re.sub(r"[^a-z0-9% ]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value


def _tokens(value):
    return set(_normalize_text(value).split())


# Common words that carry very little relationship signal.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "to",
    "in",
    "on",
    "for",
    "from",
    "by",
    "with",
    "at",
    "as",
    "is",
    "was",
    "were",
    "are",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "their",
    "there",
    "than",
    "then",
    "also",
    "both",
    "over",
    "under",
    "during",
    "between",
    "through",
    "per",
    "into",
    "which",
    "who",
    "whose",
    "reported",
}


def _meaningful_tokens(value):
    return {
        token
        for token in _tokens(value)
        if token not in _STOPWORDS and len(token) > 1
    }


# ---------------------------------------------------------------------------
# BASIC SIMILARITY
# ---------------------------------------------------------------------------

def _sequence_similarity(a, b):
    a = _normalize_text(a)
    b = _normalize_text(b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def _token_overlap(a, b):
    a_tokens = _meaningful_tokens(a)
    b_tokens = _meaningful_tokens(b)

    if not a_tokens or not b_tokens:
        return 0.0

    union = a_tokens | b_tokens

    if not union:
        return 0.0

    return len(a_tokens & b_tokens) / len(union)


def _containment_overlap(a, b):
    """
    Measures whether the smaller token set is substantially contained
    inside the larger one.

    Examples:

        "Indian exports"
        "exports"

    or:

        "total revenue"
        "revenue"
    """

    a_tokens = _meaningful_tokens(a)
    b_tokens = _meaningful_tokens(b)

    if not a_tokens or not b_tokens:
        return 0.0

    smaller = min(len(a_tokens), len(b_tokens))

    if smaller == 0:
        return 0.0

    return len(a_tokens & b_tokens) / smaller


# ---------------------------------------------------------------------------
# SUBJECT / ENTITY SIMILARITY
# ---------------------------------------------------------------------------

_METRIC_SYNONYMS = {
    "sales": "revenue",
    "net sales": "revenue",
    "total sales": "revenue",
    "total revenue": "revenue",
    "revenues": "revenue",
    "turnover": "revenue",

    "earnings": "profit",
    "net earnings": "profit",
    "net income": "profit",
    "net profit": "profit",

    "operating earnings": "operating profit",
    "operating income": "operating profit",

    "cash and cash equivalents": "cash balance",
    "cash equivalents": "cash balance",

    "imports": "imports",
    "import value": "imports",
    "import volume": "imports",

    "exports": "exports",
    "export value": "exports",
    "export volume": "exports",

    "tariff rate": "tariff",
    "tariff rates": "tariff",
    "customs duty": "tariff",
    "customs duties": "tariff",

    "inflation rate": "inflation",
    "consumer price inflation": "inflation",

    "employment rate": "employment",
    "unemployment rate": "unemployment",
}


def _canonical_metric(value):
    normalized = _normalize_text(value)

    if normalized in _METRIC_SYNONYMS:
        return _METRIC_SYNONYMS[normalized]

    return normalized


def _same_subject(a, b, threshold=0.75):
    """
    Determine whether two subjects are probably the same entity/topic.

    This is intentionally softer than the original implementation because
    real documents frequently phrase the same subject differently.
    """

    normalized_a = _normalize_text(a)
    normalized_b = _normalize_text(b)

    if not normalized_a or not normalized_b:
        return False

    if normalized_a == normalized_b:
        return True

    if _sequence_similarity(normalized_a, normalized_b) >= threshold:
        return True

    if _token_overlap(normalized_a, normalized_b) >= 0.40:
        return True

    if _containment_overlap(normalized_a, normalized_b) >= 0.60:
        return True

    return False


def _subject_similarity(a, b):
    normalized_a = _normalize_text(a)
    normalized_b = _normalize_text(b)

    if not normalized_a or not normalized_b:
        return 0.0

    if normalized_a == normalized_b:
        return 1.0

    return max(
        _sequence_similarity(normalized_a, normalized_b),
        _token_overlap(normalized_a, normalized_b),
        _containment_overlap(normalized_a, normalized_b),
    )


# ---------------------------------------------------------------------------
# PREDICATE SIMILARITY
# ---------------------------------------------------------------------------

def _canonical_predicate(value):
    normalized = _normalize_text(value)

    if normalized in _METRIC_SYNONYMS:
        return _METRIC_SYNONYMS[normalized]

    return normalized


def _same_predicate(a, b, threshold=0.75):
    canonical_a = _canonical_predicate(a)
    canonical_b = _canonical_predicate(b)

    if not canonical_a or not canonical_b:
        return False

    if canonical_a == canonical_b:
        return True

    if _sequence_similarity(canonical_a, canonical_b) >= threshold:
        return True

    if _token_overlap(canonical_a, canonical_b) >= 0.40:
        return True

    if _containment_overlap(canonical_a, canonical_b) >= 0.60:
        return True

    return False


def _predicate_similarity(a, b):
    canonical_a = _canonical_predicate(a)
    canonical_b = _canonical_predicate(b)

    if not canonical_a or not canonical_b:
        return 0.0

    if canonical_a == canonical_b:
        return 1.0

    return max(
        _sequence_similarity(canonical_a, canonical_b),
        _token_overlap(canonical_a, canonical_b),
        _containment_overlap(canonical_a, canonical_b),
    )


# ---------------------------------------------------------------------------
# UNITS / VALUE TYPES
# ---------------------------------------------------------------------------

_UNIT_ALIASES = {
    "₹": "inr",
    "rs": "inr",
    "rupees": "inr",
    "inr": "inr",

    "crore": "crore",
    "crores": "crore",
    "cr": "crore",

    "lakh": "lakh",
    "lakhs": "lakh",

    "million": "million",
    "mn": "million",

    "billion": "billion",
    "bn": "billion",

    "%": "percent",
    "percent": "percent",
    "percentage": "percent",

    "count": "count",
    "number": "count",
    "times": "time",
}


def _unit_tokens(unit):
    normalized = _normalize_text(unit)

    return {
        _UNIT_ALIASES.get(token, token)
        for token in normalized.split()
    }


def _unit_family(unit):
    tokens = _unit_tokens(unit)

    if not tokens:
        return None

    if "percent" in tokens:
        return "percent"

    if "time" in tokens:
        return "time"

    if "count" in tokens:
        return "count"

    currency_scale = {
        "crore",
        "lakh",
        "million",
        "billion",
    }

    if tokens & currency_scale:
        return "currency"

    if "inr" in tokens:
        return "currency"

    return None


def _same_unit(a, b):
    """
    Units are a scoring signal rather than a hard candidate filter.

    We don't want to eliminate potentially useful relationships simply
    because the claims use different units.
    """

    unit_a = a.get("unit")
    unit_b = b.get("unit")

    if not unit_a or not unit_b:
        return True

    normalized_a = _unit_tokens(unit_a)
    normalized_b = _unit_tokens(unit_b)

    if normalized_a == normalized_b:
        return True

    family_a = _unit_family(unit_a)
    family_b = _unit_family(unit_b)

    # Unknown dimensions should not block candidate generation.
    if family_a is None or family_b is None:
        return True

    return family_a == family_b


def _same_value_type(a, b):
    type_a = _normalize_text(a.get("value_type"))
    type_b = _normalize_text(b.get("value_type"))

    if not type_a or not type_b:
        return True

    return type_a == type_b


# ---------------------------------------------------------------------------
# CONTEXT SIMILARITY
# ---------------------------------------------------------------------------

def _field_similarity(a, b, field):
    value_a = a.get(field, "")
    value_b = b.get(field, "")

    if not value_a or not value_b:
        return 0.0

    return max(
        _sequence_similarity(value_a, value_b),
        _token_overlap(value_a, value_b),
        _containment_overlap(value_a, value_b),
    )


def _definition_similarity(a, b):
    return _field_similarity(a, b, "definition")


def _basis_similarity(a, b):
    return _field_similarity(a, b, "basis")


def _scope_similarity(a, b):
    return _field_similarity(a, b, "scope")


# ---------------------------------------------------------------------------
# PERIOD SIMILARITY
# ---------------------------------------------------------------------------

def _period_similarity(a, b):
    """
    Period is contextual information, not a hard filter.

    Same period:
        strong candidate signal.

    Different period:
        still potentially useful because the relationship adjudicator
        can classify it as RECONCILES / DIFFERENT_PERIOD.
    """

    fields = [
        "period_start",
        "period_end",
        "period_type",
    ]

    available_a = [
        str(a.get(field))
        for field in fields
        if a.get(field)
    ]

    available_b = [
        str(b.get(field))
        for field in fields
        if b.get(field)
    ]

    if not available_a or not available_b:
        return 0.0

    text_a = " ".join(available_a)
    text_b = " ".join(available_b)

    if text_a == text_b:
        return 1.0

    return max(
        _sequence_similarity(text_a, text_b),
        _token_overlap(text_a, text_b),
        _containment_overlap(text_a, text_b),
    )


# ---------------------------------------------------------------------------
# RELATIONSHIP SIGNALS
# ---------------------------------------------------------------------------

_RELATION_CUES = {
    "because",
    "due",
    "caused",
    "cause",
    "causing",
    "led",
    "leads",
    "result",
    "resulted",
    "resulting",
    "therefore",
    "following",
    "after",
    "before",
    "while",
    "whereas",
    "however",
    "despite",

    "increase",
    "increased",
    "increasing",
    "decrease",
    "decreased",
    "decline",
    "declined",
    "fall",
    "fell",
    "rose",
    "grew",
    "growth",
    "reduced",
    "reduction",

    "higher",
    "lower",
    "change",
    "changed",
    "impact",
    "effect",
    "affected",
    "contributed",
    "contribution",
    "associated",
    "correlated",
    "compared",
    "versus",
}


def _claim_text(claim):
    parts = [
        claim.get("subject", ""),
        claim.get("predicate", ""),
        claim.get("definition", ""),
        claim.get("basis", ""),
        claim.get("scope", ""),
    ]

    return " ".join(
        str(part)
        for part in parts
        if part
    )


def _relation_cue_overlap(a, b):
    tokens_a = _meaningful_tokens(_claim_text(a))
    tokens_b = _meaningful_tokens(_claim_text(b))

    cues_a = tokens_a & _RELATION_CUES
    cues_b = tokens_b & _RELATION_CUES

    return len(cues_a & cues_b)


def _shared_context_tokens(a, b):
    """
    Find meaningful tokens shared across the complete claim context.

    This allows potentially related claims with different predicates
    to become candidates.

    Example:

        "Tariff rates declined"

        "Imports increased"

    The subjects and predicates differ, but the claims may share
    meaningful contextual terms such as India, trade, policy, etc.
    """

    tokens_a = _meaningful_tokens(_claim_text(a))
    tokens_b = _meaningful_tokens(_claim_text(b))

    return tokens_a & tokens_b


# ---------------------------------------------------------------------------
# PAIR SCORING
# ---------------------------------------------------------------------------

def _candidate_score(
    claim,
    other,
    subject_threshold=0.75,
    predicate_threshold=0.75,
):
    subject_a = claim.get("subject", "")
    subject_b = other.get("subject", "")

    predicate_a = claim.get("predicate", "")
    predicate_b = other.get("predicate", "")

    subject_score = _subject_similarity(
        subject_a,
        subject_b,
    )

    predicate_score = _predicate_similarity(
        predicate_a,
        predicate_b,
    )

    definition_score = _definition_similarity(
        claim,
        other,
    )

    basis_score = _basis_similarity(
        claim,
        other,
    )

    scope_score = _scope_similarity(
        claim,
        other,
    )

    period_score = _period_similarity(
        claim,
        other,
    )

    shared_tokens = _shared_context_tokens(
        claim,
        other,
    )

    relation_cues = _relation_cue_overlap(
        claim,
        other,
    )

    same_subject = _same_subject(
        subject_a,
        subject_b,
        subject_threshold,
    )

    same_predicate = _same_predicate(
        predicate_a,
        predicate_b,
        predicate_threshold,
    )

    same_unit = _same_unit(
        claim,
        other,
    )

    same_value_type = _same_value_type(
        claim,
        other,
    )

    # ------------------------------------------------------------------
    # STRONGEST CASE
    # ------------------------------------------------------------------
    #
    # Same subject + same predicate is highly likely to be a meaningful
    # comparison. But don't blindly assign 100 because we want ranking
    # diversity.
    # ------------------------------------------------------------------

    if same_subject and same_predicate:
        score = 70.0

        score += definition_score * 12.0
        score += basis_score * 5.0
        score += scope_score * 5.0
        score += period_score * 8.0

        if shared_tokens:
            score += min(len(shared_tokens), 5) * 1.5

        if same_unit:
            score += 3.0

        if same_value_type:
            score += 2.0

        return score, "same_subject_and_predicate"

    # ------------------------------------------------------------------
    # SAME SUBJECT / DIFFERENT PREDICATE
    # ------------------------------------------------------------------
    #
    # Useful for related metrics.
    #
    # Example:
    #
    #     tariff rate decreased
    #     imports increased
    #
    # The same subject/context can still make this worth adjudicating.
    # ------------------------------------------------------------------

    if same_subject:
        score = 45.0

        score += predicate_score * 12.0
        score += definition_score * 12.0
        score += basis_score * 5.0
        score += scope_score * 5.0
        score += period_score * 6.0

        if shared_tokens:
            score += min(len(shared_tokens), 5) * 2.0

        if relation_cues:
            score += min(relation_cues, 3) * 3.0

        if same_unit:
            score += 2.0

        if same_value_type:
            score += 1.0

        return score, "same_subject_related_predicate"

    # ------------------------------------------------------------------
    # DIFFERENT SUBJECT / SHARED CONTEXT
    # ------------------------------------------------------------------
    #
    # More conservative because unrelated claims can share generic
    # contextual words.
    # ------------------------------------------------------------------

    shared_token_count = len(shared_tokens)

    score = 0.0

    if shared_token_count >= 4:
        score += 28.0
    elif shared_token_count == 3:
        score += 23.0
    elif shared_token_count == 2:
        score += 16.0
    elif shared_token_count == 1:
        score += 5.0

    score += subject_score * 12.0
    score += predicate_score * 8.0
    score += definition_score * 18.0
    score += basis_score * 5.0
    score += scope_score * 5.0
    score += period_score * 5.0

    if relation_cues:
        score += min(relation_cues, 3) * 4.0

    if same_unit:
        score += 2.0

    if same_value_type:
        score += 1.0

    return score, "shared_context"


# ---------------------------------------------------------------------------
# PUBLIC PAIR SCORING API
# ---------------------------------------------------------------------------

def score_candidate_pair(
    claim,
    other,
    subject_threshold=0.75,
    predicate_threshold=0.75,
):
    """
    Score a single pair.

    Returns:

        (score, reason)

    A score <= 0 means the pair should not be considered.
    """

    # Never compare a claim with itself.
    if claim.get("id") == other.get("id"):
        return 0.0, "same_claim"

    # Candidate generation is cross-document only.
    document_a = claim.get("document_id")
    document_b = other.get("document_id")

    if (
        document_a
        and document_b
        and document_a == document_b
    ):
        return 0.0, "same_document"

    score, reason = _candidate_score(
        claim,
        other,
        subject_threshold,
        predicate_threshold,
    )

    if score < MIN_CANDIDATE_SCORE:
        return 0.0, "below_threshold"

    return score, reason


# ---------------------------------------------------------------------------
# GLOBAL CANDIDATE RANKING
# ---------------------------------------------------------------------------

def rank_candidates(
    claims,
    max_candidates=MAX_CANDIDATES,
    subject_threshold=0.75,
    predicate_threshold=0.75,
):
    """
    Score all cross-document claim pairs and keep only the strongest ones.

    This is the main candidate-generation API used by the relationship
    pipeline.

    Example:

        176 claims
            ↓
        possible cross-document pairs
            ↓
        scoring
            ↓
        top 150
            ↓
        Gemini adjudication
    """

    scored = []

    for i, claim_a in enumerate(claims):

        for claim_b in claims[i + 1:]:

            score, reason = score_candidate_pair(
                claim_a,
                claim_b,
                subject_threshold,
                predicate_threshold,
            )

            if score <= 0:
                continue

            scored.append(
                (
                    claim_a,
                    claim_b,
                    score,
                    reason,
                )
            )

    # Strongest pairs first.
    scored.sort(
        key=lambda item: item[2],
        reverse=True,
    )

    selected = scored[:max_candidates]

    print(
        "[Candidates] "
        f"{len(scored)} plausible pairs → "
        f"top {len(selected)} selected"
    )

    if selected:
        print(
            "[Candidates] "
            f"score range: "
            f"{selected[-1][2]:.1f} - "
            f"{selected[0][2]:.1f}"
        )

    return selected


# ---------------------------------------------------------------------------
# BACKWARD-COMPATIBLE API
# ---------------------------------------------------------------------------

def find_candidates(
    claim,
    other_claims,
    subject_threshold=0.75,
    predicate_threshold=0.75,
):
    """
    Backwards-compatible API.

    This remains available for any existing code that expects:

        find_candidates(claim, other_claims)

    For the session-wide relationship pipeline, prefer:

        rank_candidates(claims)
    """

    candidates = []

    for other in other_claims:

        score, _ = score_candidate_pair(
            claim,
            other,
            subject_threshold,
            predicate_threshold,
        )

        if score <= 0:
            continue

        candidates.append(other)

    return candidates