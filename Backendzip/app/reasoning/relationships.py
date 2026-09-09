from app.normalization.normalize import (
    values_match,
    normalize_period,
    periods_comparable,
)
from app.reasoning.llm import judge_relationship


def evaluate_pair(claim_a: dict, claim_b: dict) -> dict:
    deterministic_result = _evaluate_pair_without_llm(claim_a, claim_b)
    if deterministic_result is not None:
        return deterministic_result
    return _judge_with_llm(claim_a, claim_b)


def evaluate_pairs(pairs):
    deterministic_results = []
    llm_pairs = []

    for claim_a, claim_b in pairs:
        result = _evaluate_pair_without_llm(claim_a, claim_b)

        if result is None:
            llm_pairs.append((claim_a, claim_b))
            continue

        deterministic_results.append({
            "source_claim_id": claim_a["id"],
            "target_claim_id": claim_b["id"],
            "relationship_type": result["relationship_type"],
            "reason_code": result["reason_code"],
            "explanation": result["explanation"],
            "confidence": result.get("confidence"),
            "decided_by": result.get("decided_by", "rules"),
        })

    print(
        "[Relationships] "
        f"{len(pairs)} candidate pairs → "
        f"{len(deterministic_results)} deterministic, "
        f"{len(llm_pairs)} require LLM"
    )

    return deterministic_results, llm_pairs


def _evaluate_pair_without_llm(claim_a, claim_b):
    subject_a = (claim_a.get("subject") or "").strip().lower()
    subject_b = (claim_b.get("subject") or "").strip().lower()
    predicate_a = (claim_a.get("predicate") or "").strip().lower()
    predicate_b = (claim_b.get("predicate") or "").strip().lower()

    if not subject_a or not subject_b:
        return None
    if not predicate_a or not predicate_b:
        return None
    if subject_a != subject_b:
        return None
    if predicate_a != predicate_b:
        return None

    scope_a = (claim_a.get("scope") or "").strip().lower()
    scope_b = (claim_b.get("scope") or "").strip().lower()

    if scope_a and scope_b and scope_a != scope_b:
        return _verdict(
            "RECONCILES",
            "DIFFERENT_SCOPE",
            f"'{claim_a.get('subject', '')}' reports the same metric on "
            f"different scopes ({scope_a} vs {scope_b}).",
            0.8,
            "rules",
        )

    period_start_a = claim_a.get("period_start")
    period_end_a = claim_a.get("period_end")
    period_start_b = claim_b.get("period_start")
    period_end_b = claim_b.get("period_end")

    if (
        period_start_a
        and period_start_b
        and period_end_a
        and period_end_b
        and (
            period_start_a != period_start_b
            or period_end_a != period_end_b
        )
    ):
        return _verdict(
            "RECONCILES",
            "DIFFERENT_PERIOD",
            f"Periods differ ({period_start_a} to {period_end_a} vs "
            f"{period_start_b} to {period_end_b}); the claims refer to "
            "different reporting periods.",
            0.85,
            "rules",
        )

    if not (
        period_start_a
        and period_start_b
        and period_end_a
        and period_end_b
    ):
        period_a = normalize_period(
            f"{period_start_a or ''} "
            f"{period_end_a or ''} "
            f"{claim_a.get('period_type') or ''}"
        )
        period_b = normalize_period(
            f"{period_start_b or ''} "
            f"{period_end_b or ''} "
            f"{claim_b.get('period_type') or ''}"
        )

        comparable, _ = periods_comparable(period_a, period_b)

        if not comparable:
            return _verdict(
                "RECONCILES",
                "DIFFERENT_PERIOD",
                f"Periods differ ({period_a['raw']} vs "
                f"{period_b['raw']}); the claims refer to "
                "different reporting periods.",
                0.85,
                "rules",
            )

    basis_a = (claim_a.get("basis") or "").strip().lower()
    basis_b = (claim_b.get("basis") or "").strip().lower()

    if basis_a and basis_b and basis_a != basis_b:
        return None

    # Different explicit definitions make the pair semantically ambiguous.
    # Send it to the LLM even if the numeric values happen to agree.
    def_a = (claim_a.get("definition") or "").strip().lower()
    def_b = (claim_b.get("definition") or "").strip().lower()

    if def_a and def_b and def_a != def_b:
        return None

    if (
        claim_a.get("value") is not None
        and claim_b.get("value") is not None
        and claim_a.get("unit")
        and claim_b.get("unit")
    ):
        match, num_reason = values_match(
            claim_a["value"],
            claim_a["unit"],
            claim_b["value"],
            claim_b["unit"],
        )

        if match:
            return _verdict(
                "CORROBORATES",
                num_reason,
                "Values agree once normalized to a common "
                f"unit ({num_reason.lower()}).",
                0.9,
                "rules",
            )

    return None


def _same_metric_deterministically(claim_a, claim_b):
    subject_a = (claim_a.get("subject") or "").strip().lower()
    subject_b = (claim_b.get("subject") or "").strip().lower()
    predicate_a = (claim_a.get("predicate") or "").strip().lower()
    predicate_b = (claim_b.get("predicate") or "").strip().lower()

    if not subject_a or not subject_b:
        return False
    if not predicate_a or not predicate_b:
        return False

    return subject_a == subject_b and predicate_a == predicate_b


def _judge_with_llm(claim_a, claim_b):
    verdict = judge_relationship(claim_a, claim_b)
    verdict["decided_by"] = "llm"
    return verdict


def _verdict(rel_type, reason_code, explanation, confidence, decided_by):
    return {
        "relationship_type": rel_type,
        "reason_code": reason_code,
        "explanation": explanation,
        "confidence": confidence,
        "decided_by": decided_by,
    }
