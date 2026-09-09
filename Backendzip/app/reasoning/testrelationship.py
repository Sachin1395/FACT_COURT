import pytest

from relationships import (
    evaluate_pair,
    evaluate_pairs,
    _evaluate_pair_without_llm,
)


def make_claim(
    claim_id="1",
    document_id="doc1",
    subject="Apple Inc.",
    predicate="revenue",
    value=394,
    value_type="numeric",
    unit="billion USD",
    period_start=None,
    period_end=None,
    period_type=None,
    scope=None,
    basis=None,
    definition=None,
):
    return {
        "id": claim_id,
        "document_id": document_id,
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "value_type": value_type,
        "unit": unit,
        "period_start": period_start,
        "period_end": period_end,
        "period_type": period_type,
        "scope": scope,
        "basis": basis,
        "definition": definition,
    }


# ---------------------------------------------------------
# Deterministic relationship tests
# ---------------------------------------------------------

def test_exact_same_metric_and_value_corroborrates():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is not None
    assert result["relationship_type"] == "CORROBORATES"


def test_different_period_reconciles():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="revenue",
        value=383,
        unit="billion USD",
        period_start="2023-01-01",
        period_end="2023-12-31",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is not None
    assert result["relationship_type"] == "RECONCILES"
    assert result["reason_code"] == "DIFFERENT_PERIOD"


def test_different_scope_reconciles():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Microsoft",
        predicate="revenue",
        value=100,
        unit="million USD",
        scope="Cloud segment",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Microsoft",
        predicate="revenue",
        value=500,
        unit="million USD",
        scope="Total company",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is not None
    assert result["relationship_type"] == "RECONCILES"
    assert result["reason_code"] == "DIFFERENT_SCOPE"


def test_unit_normalization_can_corroborrate():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="cash balance",
        value=1266,
        unit="₹ million",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="cash balance",
        value=126.6,
        unit="₹ crore",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is not None
    assert result["relationship_type"] == "CORROBORATES"


# ---------------------------------------------------------
# Important semantic-safety tests
# ---------------------------------------------------------

def test_different_metric_does_not_get_scope_reconciliation():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
        scope="Consolidated",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="cash balance",
        value=30,
        unit="billion USD",
        scope="Standalone",
    )

    # Metric identity is ambiguous/different, so deterministic
    # rules must not incorrectly call this DIFFERENT_SCOPE.
    result = _evaluate_pair_without_llm(a, b)

    assert result is None


def test_different_metric_does_not_get_definition_reconciliation():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
        definition="Total net sales",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="cash balance",
        value=30,
        unit="billion USD",
        definition="Cash and cash equivalents at year end",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is None


def test_different_definition_is_delegated_to_llm():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="profit",
        value=50,
        unit="million USD",
        definition="Profit before tax",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="profit",
        value=50,
        unit="million USD",
        definition="Profit after tax",
    )

    # The deterministic layer should not assume that textual
    # inequality alone proves DIFFERENT_DEFINITION.
    result = _evaluate_pair_without_llm(a, b)

    assert result is None


def test_different_basis_is_delegated_to_llm():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        basis="GAAP",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        basis="Non-GAAP",
    )

    # Basis difference is not automatically an estimate vintage.
    result = _evaluate_pair_without_llm(a, b)

    assert result is None


# ---------------------------------------------------------
# LLM delegation tests
# ---------------------------------------------------------

def test_ambiguous_pair_is_sent_to_llm(monkeypatch):
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="net sales",
        value=394,
        unit="billion USD",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple",
        predicate="total revenue",
        value=394,
        unit="billion USD",
    )

    def fake_judge_relationship(claim_a, claim_b):
        assert claim_a["id"] == "1"
        assert claim_b["id"] == "2"

        return {
            "relationship_type": "CORROBORATES",
            "reason_code": "EXACT_MATCH",
            "explanation": "Both claims describe the same revenue metric.",
            "confidence": 0.95,
        }

    monkeypatch.setattr(
        "app.matching.relationships.judge_relationship",
        fake_judge_relationship,
    )

    result = evaluate_pair(a, b)

    assert result["relationship_type"] == "CORROBORATES"
    assert result["reason_code"] == "EXACT_MATCH"
    assert result["decided_by"] == "llm"


def test_llm_result_gets_decided_by_llm(monkeypatch):
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=120,
        unit="million USD",
    )

    def fake_judge_relationship(claim_a, claim_b):
        return {
            "relationship_type": "CONTRADICTS",
            "reason_code": "NUMERIC_DISCREPANCY",
            "explanation": "Same metric and period but materially different values.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(
        "app.matching.relationships.judge_relationship",
        fake_judge_relationship,
    )

    result = evaluate_pair(a, b)

    assert result["relationship_type"] == "CONTRADICTS"
    assert result["reason_code"] == "NUMERIC_DISCREPANCY"
    assert result["decided_by"] == "llm"


# ---------------------------------------------------------
# Missing-information tests
# ---------------------------------------------------------

def test_missing_value_does_not_create_contradiction():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=None,
        unit="million USD",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is None


def test_missing_unit_does_not_create_contradiction():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit=None,
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is None


def test_missing_definition_does_not_block_exact_value_match():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        definition=None,
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        definition="Total revenue",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is not None
    assert result["relationship_type"] == "CORROBORATES"


# ---------------------------------------------------------
# Batch evaluation tests
# ---------------------------------------------------------

def test_evaluate_pairs_separates_deterministic_and_llm_pairs(monkeypatch):
    deterministic_a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    deterministic_b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    llm_a = make_claim(
        claim_id="3",
        document_id="doc3",
        subject="Apple Inc.",
        predicate="net sales",
        value=394,
        unit="billion USD",
    )

    llm_b = make_claim(
        claim_id="4",
        document_id="doc4",
        subject="Apple",
        predicate="total revenue",
        value=394,
        unit="billion USD",
    )

    deterministic_results, llm_pairs = evaluate_pairs(
        [
            (deterministic_a, deterministic_b),
            (llm_a, llm_b),
        ]
    )

    assert len(deterministic_results) == 1
    assert len(llm_pairs) == 1

    assert deterministic_results[0]["source_claim_id"] == "1"
    assert deterministic_results[0]["target_claim_id"] == "2"

    assert llm_pairs[0][0]["id"] == "3"
    assert llm_pairs[0][1]["id"] == "4"


def test_deterministic_result_contains_required_fields():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    results, llm_pairs = evaluate_pairs([(a, b)])

    assert len(llm_pairs) == 0
    assert len(results) == 1

    result = results[0]

    assert result["source_claim_id"] == "1"
    assert result["target_claim_id"] == "2"
    assert result["relationship_type"] == "CORROBORATES"
    assert result["reason_code"]
    assert result["explanation"]
    assert result["confidence"] is not None
    assert result["decided_by"] == "rules"


# ---------------------------------------------------------
# Safety tests for unsupported deterministic assumptions
# ---------------------------------------------------------

def test_same_subject_same_predicate_different_values_go_to_llm():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=120,
        unit="million USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    result = _evaluate_pair_without_llm(a, b)

    # Numeric disagreement is not automatically contradiction.
    assert result is None


def test_empty_subject_or_predicate_goes_to_llm():
    a = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    b = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    result = _evaluate_pair_without_llm(a, b)

    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
