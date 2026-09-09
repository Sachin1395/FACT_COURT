"""
Candidate generation for cross-document claim matching.

Candidate generation answers only:

    "Could these two claims describe the same underlying
     metric or fact?"

It does NOT decide:
    CORROBORATES
    CONTRADICTS
    RECONCILES
    UNCERTAIN

Those decisions are handled later by the deterministic
relationship rules and LLM adjudication.

Design goals:
- Avoid comparing unrelated metrics.
- Allow different reporting periods.
- Allow different units when the underlying metric is the same.
- Allow different wording for the same metric.
- Avoid generic one-word subjects acting as wildcards.
- Use definitions/context as an additional filter.
"""

import re
from difflib import SequenceMatcher


# ============================================================
# NORMALIZATION
# ============================================================

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "by",
    "from",
    "and",
    "or",
    "as",
    "with",
    "during",
    "over",
    "per",
}


def _normalize_text(value) -> str:
    """
    Normalize text for semantic/token comparison.

    This is deliberately conservative:
    we normalize formatting but do not aggressively
    rewrite the meaning of the claim.
    """

    if value is None:
        return ""

    text = str(value).lower()

    # Unicode punctuation normalization
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("−", "-")
    text = text.replace("’", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')

    # Common separators
    text = text.replace("_", " ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")

    # Remove punctuation
    text = re.sub(r"[^a-z0-9.% ]+", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _tokens(value) -> set[str]:
    """
    Return normalized content tokens.

    Stopwords are removed so phrases such as:

        "revenue from operations"
        "revenue of operations"

    are easier to compare.
    """

    text = _normalize_text(value)

    if not text:
        return set()

    return {
        token
        for token in text.split()
        if token not in _STOPWORDS
    }


# ============================================================
# SIMILARITY
# ============================================================

def _similar(a, b, threshold=0.75) -> bool:
    """
    Character-level similarity.

    Useful when two labels differ slightly, e.g.

        "revenue from operations"
        "revenue from operation"
    """

    a = _normalize_text(a)
    b = _normalize_text(b)

    if not a or not b:
        return False

    return SequenceMatcher(None, a, b).ratio() >= threshold


def _token_overlap(a, b) -> float:
    """
    Jaccard token similarity.

        intersection / union

    IMPORTANT:
    Do NOT use intersection / min(len(a), len(b)).

    The latter allows a generic one-token subject such as
    "cash" or "revenue" to behave like a wildcard.
    """

    a_tokens = _tokens(a)
    b_tokens = _tokens(b)

    if not a_tokens or not b_tokens:
        return 0.0

    union = a_tokens | b_tokens

    if not union:
        return 0.0

    return len(a_tokens & b_tokens) / len(union)


# ============================================================
# CANONICALIZATION
# ============================================================

def _canonicalize_predicate(value) -> str:
    """
    Normalize predicate wording.

    Keep this lightweight. The LLM should ultimately determine
    semantic equivalence for ambiguous cases.
    """

    text = _normalize_text(value)

    replacements = {
        "grew": "growth",
        "growth rate": "growth",
        "increased": "increase",
        "increasing": "increase",
        "decreased": "decrease",
        "decreasing": "decrease",
    }

    for source, target in replacements.items():
        text = text.replace(source, target)

    return re.sub(r"\s+", " ", text).strip()


def _canonicalize_subject(value) -> str:
    """
    Normalize subject wording without trying to infer meaning.
    """

    return re.sub(
        r"\s+",
        " ",
        _normalize_text(value),
    ).strip()


# ============================================================
# SUBJECT MATCHING
# ============================================================

def _same_subject(a, b, threshold=0.75) -> bool:
    """
    Determine whether two subjects are plausible matches.

    For normal multi-token subjects:
        - character similarity OR
        - Jaccard token overlap

    For one-token subjects:
        - require direct similarity

    This prevents generic terms such as:
        "cash"
        "revenue"
        "value"

    from becoming wildcards.
    """

    canonical_a = _canonicalize_subject(a)
    canonical_b = _canonicalize_subject(b)

    if not canonical_a or not canonical_b:
        return False

    a_tokens = _tokens(canonical_a)
    b_tokens = _tokens(canonical_b)

    # Short/generic subjects need stricter matching.
    if min(len(a_tokens), len(b_tokens)) < 2:
        return _similar(
            canonical_a,
            canonical_b,
            threshold,
        )

    return (
        _similar(
            canonical_a,
            canonical_b,
            threshold,
        )
        or
        _token_overlap(
            canonical_a,
            canonical_b,
        ) >= 0.60
    )


# ============================================================
# PREDICATE MATCHING
# ============================================================

def _same_predicate(a, b, threshold=0.75) -> bool:
    """
    Determine whether two predicates are plausibly equivalent.

    IMPORTANT:
    Missing predicates are NOT automatically considered
    compatible.

    Treating missing information as True creates many false
    candidate pairs.
    """

    canonical_a = _canonicalize_predicate(a)
    canonical_b = _canonicalize_predicate(b)

    if not canonical_a or not canonical_b:
        return False

    a_tokens = _tokens(canonical_a)
    b_tokens = _tokens(canonical_b)

    if min(len(a_tokens), len(b_tokens)) < 2:
        return _similar(
            canonical_a,
            canonical_b,
            threshold,
        )

    return (
        _similar(
            canonical_a,
            canonical_b,
            threshold,
        )
        or
        _token_overlap(
            canonical_a,
            canonical_b,
        ) >= 0.60
    )


# ============================================================
# VALUE / UNIT COMPATIBILITY
# ============================================================

def _normalize_unit(unit) -> str:
    """
    Normalize common unit spellings.
    """

    if unit is None:
        return ""

    text = _normalize_text(unit)

    aliases = {
        "percent": "%",
        "percentage": "%",
        "pct": "%",
        "crore": "cr",
        "crores": "cr",
        "rs": "inr",
        "₹": "inr",
        "rupees": "inr",
        "million": "mn",
        "millions": "mn",
        "billion": "bn",
        "billions": "bn",
    }

    return aliases.get(text, text)


def _value_type_compatible(a, b) -> bool:
    """
    Reject clearly incompatible value types.

    Missing value types are allowed because extraction may not
    always provide them.
    """

    a_type = _normalize_text(a.get("value_type"))
    b_type = _normalize_text(b.get("value_type"))

    if not a_type or not b_type:
        return True

    return a_type == b_type


def _unit_compatible(a, b) -> bool:
    """
    Units are allowed to differ.

    Example:

        ₹1,266 million
        ₹126.6 crore

    can describe the same underlying fact.

    We therefore do NOT reject a pair simply because units
    differ.

    We only reject obviously incompatible qualitative units.
    """

    unit_a = _normalize_unit(a.get("unit"))
    unit_b = _normalize_unit(b.get("unit"))

    if not unit_a or not unit_b:
        return True

    if unit_a == unit_b:
        return True

    # Numeric monetary/scaled units can be normalized later.
    numeric_units = {
        "inr",
        "cr",
        "mn",
        "bn",
        "million",
        "billion",
        "thousand",
        "lakh",
    }

    if unit_a in numeric_units and unit_b in numeric_units:
        return True

    # Percent-like units
    percentage_units = {
        "%",
        "percent",
        "percentage",
        "pct",
    }

    if unit_a in percentage_units and unit_b in percentage_units:
        return True

    # Multiples such as x
    if unit_a == "x" and unit_b == "x":
        return True

    # If either unit is unknown, allow the LLM to decide.
    return True


# ============================================================
# PERIOD COMPATIBILITY
# ============================================================

def _period_compatible(a, b) -> bool:
    """
    Period differences are NOT a reason to reject candidates.

    Example:

        FY2024 revenue = ₹8,142 crore
        Q4 FY2024 revenue = ₹2,076 crore

    These may concern the same metric but different scopes.

    The relationship layer will later classify such a pair as
    RECONCILES / DIFFERENT_PERIOD when appropriate.
    """

    return True


# ============================================================
# DEFINITION COMPATIBILITY
# ============================================================

def _definition_compatible(a, b) -> bool:
    """
    Use definitions as a conservative semantic filter.

    If neither claim has a definition:
        allow.

    If only one has a definition:
        allow.

    If both have definitions:
        reject only when they are strongly different.

    This is intentionally conservative because different
    wording does not necessarily mean different definitions.
    """

    definition_a = a.get("definition")
    definition_b = b.get("definition")

    if not definition_a or not definition_b:
        return True

    a_text = _normalize_text(definition_a)
    b_text = _normalize_text(definition_b)

    if not a_text or not b_text:
        return True

    similarity = SequenceMatcher(
        None,
        a_text,
        b_text,
    ).ratio()

    # Very different definitions are unlikely to be
    # the same metric.
    if similarity < 0.35:
        return False

    return True


# ============================================================
# MAIN CANDIDATE TEST
# ============================================================

def _is_candidate(claim_a, claim_b) -> bool:
    """
    Decide whether two claims should be sent downstream
    for relationship evaluation.
    """

    # --------------------------------------------------------
    # Subject
    # --------------------------------------------------------

    if not _same_subject(
        claim_a.get("subject", ""),
        claim_b.get("subject", ""),
    ):
        return False

    # --------------------------------------------------------
    # Predicate
    # --------------------------------------------------------

    if not _same_predicate(
        claim_a.get("predicate", ""),
        claim_b.get("predicate", ""),
    ):
        return False

    # --------------------------------------------------------
    # Value type
    # --------------------------------------------------------

    if not _value_type_compatible(
        claim_a,
        claim_b,
    ):
        return False

    # --------------------------------------------------------
    # Unit
    # --------------------------------------------------------

    if not _unit_compatible(
        claim_a,
        claim_b,
    ):
        return False

    # --------------------------------------------------------
    # Period
    # --------------------------------------------------------

    if not _period_compatible(
        claim_a,
        claim_b,
    ):
        return False

    # --------------------------------------------------------
    # Definition
    # --------------------------------------------------------

    if not _definition_compatible(
        claim_a,
        claim_b,
    ):
        return False

    return True


# ============================================================
# PUBLIC API
# ============================================================

def find_candidates(
    claim: dict,
    existing_claims: list[dict],
) -> list[dict]:
    """
    Find existing claims that could describe the same
    underlying metric/fact.

    Candidate generation is deliberately broader than
    deterministic relationship evaluation.

    The output is a list of existing claim dictionaries.
    """

    candidates = []

    for existing in existing_claims:

        # Never compare a claim with itself.
        if claim.get("id") == existing.get("id"):
            continue

        if _is_candidate(
            claim,
            existing,
        ):
            candidates.append(existing)

    return candidates


# ============================================================
# OPTIONAL DEBUG HELPER
# ============================================================

def debug_candidate_match(
    claim: dict,
    existing_claims: list[dict],
) -> list[dict]:
    """
    Debug helper for development.

    Returns detailed information about why each existing
    claim did or did not become a candidate.

    This does not affect normal pipeline behaviour.
    """

    results = []

    for existing in existing_claims:

        if claim.get("id") == existing.get("id"):
            continue

        subject_match = _same_subject(
            claim.get("subject", ""),
            existing.get("subject", ""),
        )

        predicate_match = _same_predicate(
            claim.get("predicate", ""),
            existing.get("predicate", ""),
        )

        value_type_match = _value_type_compatible(
            claim,
            existing,
        )

        unit_match = _unit_compatible(
            claim,
            existing,
        )

        period_match = _period_compatible(
            claim,
            existing,
        )

        definition_match = _definition_compatible(
            claim,
            existing,
        )

        candidate = (
            subject_match
            and predicate_match
            and value_type_match
            and unit_match
            and period_match
            and definition_match
        )

        results.append(
            {
                "existing_claim_id": existing.get("id"),
                "existing_subject": existing.get("subject"),
                "existing_predicate": existing.get("predicate"),
                "subject_match": subject_match,
                "predicate_match": predicate_match,
                "value_type_match": value_type_match,
                "unit_match": unit_match,
                "period_match": period_match,
                "definition_match": definition_match,
                "candidate": candidate,
            }
        )

    return results