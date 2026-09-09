import pytest

from candidates import find_candidates


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
    scope=None,
    basis=None,
    definition=None,
    claim_type=None,
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
        "scope": scope,
        "basis": basis,
        "definition": definition,
        "claim_type": claim_type,
    }


def get_ids(claim, others):
    return {
        c["id"]
        for c in find_candidates(
            claim,
            others,
        )
    }


# ---------------------------------------------------------
# Positive candidate cases
# ---------------------------------------------------------

def test_exact_same_metric_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="reported revenue",
        value=394.3,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
        definition="Total net sales for the fiscal year",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="reported revenue",
        value=394.3,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
        definition="Total net sales for the fiscal year",
    )

    assert "2" in get_ids(claim, [other])


def test_same_metric_different_period_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="revenue",
        value=383,
        period_start="2023-01-01",
        period_end="2023-12-31",
    )

    assert "2" in get_ids(claim, [other])


def test_same_metric_different_scope_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Microsoft",
        predicate="revenue",
        value=100,
        unit="million USD",
        scope="Cloud segment",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Microsoft",
        predicate="revenue",
        value=500,
        unit="million USD",
        scope="Total company",
    )

    assert "2" in get_ids(claim, [other])


def test_convertible_currency_units_are_candidates():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="cash balance",
        value=1266,
        unit="₹ million",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="cash balance",
        value=126.6,
        unit="₹ crore",
    )

    assert "2" in get_ids(claim, [other])


def test_same_metric_with_conflicting_values_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Tesla",
        predicate="revenue",
        value=100,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Tesla",
        predicate="revenue",
        value=120,
        unit="billion USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    assert "2" in get_ids(claim, [other])


def test_same_metric_different_wording_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="net sales",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple",
        predicate="total revenue",
        value=394,
        unit="billion USD",
    )

    assert "2" in get_ids(claim, [other])


def test_similar_definition_wording_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="operating profit",
        value=50,
        unit="million USD",
        definition="Profit from normal business operations",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="operating profit",
        value=50,
        unit="million USD",
        definition=(
            "Income generated from the company's ordinary "
            "operating activities"
        ),
    )

    assert "2" in get_ids(claim, [other])


# ---------------------------------------------------------
# Negative candidate cases
# ---------------------------------------------------------

def test_same_company_different_metric_is_not_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="cash balance",
        value=30,
        unit="billion USD",
    )

    assert "2" not in get_ids(claim, [other])


def test_different_companies_are_not_candidates():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Microsoft Corporation",
        predicate="revenue",
        value=245,
        unit="billion USD",
    )

    assert "2" not in get_ids(claim, [other])


def test_different_document_same_claim_is_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    assert "2" in get_ids(claim, [other])


def test_same_document_claim_is_skipped():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    assert "2" not in get_ids(claim, [other])


def test_self_claim_is_skipped():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    assert "1" not in get_ids(claim, [claim])


def test_incompatible_units_are_not_candidates():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=25,
        unit="percent",
    )

    assert "2" not in get_ids(claim, [other])


def test_incompatible_value_types_are_not_candidates():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=394,
        value_type="numeric",
        unit="million USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value="high",
        value_type="text",
        unit="million USD",
    )

    assert "2" not in get_ids(claim, [other])


def test_clearly_incompatible_definitions_are_not_candidates():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="profit",
        value=50,
        unit="million USD",
        definition="Profit before tax",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="profit",
        value=50,
        unit="million USD",
        definition="Profit after tax",
    )

    assert "2" not in get_ids(claim, [other])


# ---------------------------------------------------------
# Edge / recall cases
# ---------------------------------------------------------

def test_missing_period_does_not_block_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=110,
        unit="million USD",
        period_start="2024-01-01",
        period_end="2024-12-31",
    )

    assert "2" in get_ids(claim, [other])


def test_missing_definition_does_not_block_candidate():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
    )

    other = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Company X",
        predicate="revenue",
        value=100,
        unit="million USD",
        definition="Total revenue generated during the year",
    )

    assert "2" in get_ids(claim, [other])


def test_multiple_candidates_are_returned():
    claim = make_claim(
        claim_id="1",
        document_id="doc1",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other_1 = make_claim(
        claim_id="2",
        document_id="doc2",
        subject="Apple Inc.",
        predicate="revenue",
        value=394,
        unit="billion USD",
    )

    other_2 = make_claim(
        claim_id="3",
        document_id="doc3",
        subject="Apple",
        predicate="net sales",
        value=383,
        unit="billion USD",
    )

    other_3 = make_claim(
        claim_id="4",
        document_id="doc4",
        subject="Microsoft",
        predicate="revenue",
        value=245,
        unit="billion USD",
    )

    ids = get_ids(claim, [other_1, other_2, other_3])

    assert "2" in ids
    assert "3" in ids
    assert "4" not in ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
