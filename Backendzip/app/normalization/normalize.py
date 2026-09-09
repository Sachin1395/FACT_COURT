"""
Deterministic normalization helpers for claim relationship evaluation.

These helpers handle straightforward unit and period normalization
without requiring an LLM, keeping obvious results reproducible and cheap.
"""

import re


# ---------------------------------------------------------------------------
# Currency / magnitude normalization
# ---------------------------------------------------------------------------

# Canonical representation:
# (currency, value in base currency units)
_UNIT_FACTORS = {
    "inr": ("INR", 1.0),
    "inr_lakh": ("INR", 100_000.0),
    "inr_million": ("INR", 1_000_000.0),
    "inr_crore": ("INR", 10_000_000.0),
    "inr_billion": ("INR", 1_000_000_000.0),

    "usd": ("USD", 1.0),
    "usd_million": ("USD", 1_000_000.0),
    "usd_billion": ("USD", 1_000_000_000.0),
}


def _normalize_unit_key(unit: str) -> str:
    key = unit.strip().lower()

    # Currency symbols / common currency names.
    key = key.replace("₹", "inr")
    key = key.replace("$", "usd")
    key = key.replace("rs.", "inr")
    key = key.replace("rs", "inr")
    key = key.replace("rupees", "inr")
    key = key.replace("rupee", "inr")
    key = key.replace("usd", "usd")
    key = key.replace("inr", "inr")

    # Normalize common textual forms.
    key = key.replace("us dollars", "usd")
    key = key.replace("us dollar", "usd")
    key = key.replace("dollars", "usd")
    key = key.replace("dollar", "usd")

    key = key.replace("crores", "crore")
    key = key.replace("cr", "crore")
    key = key.replace("millions", "million")
    key = key.replace("mn", "million")
    key = key.replace("billions", "billion")
    key = key.replace("bn", "billion")
    key = key.replace("lakhs", "lakh")
    key = key.replace("lacs", "lakh")
    key = key.replace("lac", "lakh")

    key = re.sub(r"\s+", "_", key)
    key = re.sub(r"_+", "_", key)
    key = key.strip("_")

    # Bare magnitude units with an explicit currency are expected to
    # arrive as e.g. "billion USD" -> "billion_usd". Convert those
    # into the canonical currency-first form.
    parts = key.split("_")

    if len(parts) == 2:
        if parts[0] in {"million", "billion", "crore", "lakh"} and parts[1] in {
            "inr",
            "usd",
        }:
            key = f"{parts[1]}_{parts[0]}"

    return key


def _unit_info(unit: str):
    key = _normalize_unit_key(unit)
    return _UNIT_FACTORS.get(key)


def values_match(
    value_a: float,
    unit_a: str,
    value_b: float,
    unit_b: str,
    rel_tolerance: float = 0.02,
) -> tuple[bool, str]:
    """
    Compare two numeric values after magnitude normalization.

    Different currencies are never converted automatically because
    FX conversion requires a date/rate context that is not present
    in the claim fields.

    A difference within rel_tolerance is treated as ROUNDING.
    """

    info_a = _unit_info(unit_a)
    info_b = _unit_info(unit_b)

    if info_a is None or info_b is None:
        return False, "UNIT_UNRECOGNIZED"

    currency_a, factor_a = info_a
    currency_b, factor_b = info_b

    if currency_a != currency_b:
        return False, "UNIT_INCOMPATIBLE"

    base_a = float(value_a) * factor_a
    base_b = float(value_b) * factor_b

    if base_a == base_b:
        if _normalize_unit_key(unit_a) == _normalize_unit_key(unit_b):
            return True, "EXACT_MATCH"

        return True, "UNIT_NORMALIZATION"

    denom = max(abs(base_a), abs(base_b), 1e-9)
    rel_diff = abs(base_a - base_b) / denom

    if rel_diff <= rel_tolerance:
        return True, "ROUNDING"

    return False, "NUMERIC_DISCREPANCY"


# ---------------------------------------------------------------------------
# Fiscal period normalization
# ---------------------------------------------------------------------------

_FY_PATTERNS = [
    re.compile(r"FY\s?(\d{2,4})[-–/](\d{2,4})", re.I),
    re.compile(r"FY\s?(\d{2,4})", re.I),
    re.compile(r"(\d{4})-(\d{2,4})", re.I),
]

_QUARTER_MAP = {
    "Q1": (4, 6),
    "Q2": (7, 9),
    "Q3": (10, 12),
    "Q4": (1, 3),
}


def normalize_period(raw: str) -> dict:
    """
    Best-effort normalization of a period string.

    Supports fiscal-year labels and textual quarter/full-year periods.
    Structured ISO claim dates are handled directly by the relationship
    evaluator rather than being reparsed here.
    """

    raw = raw.strip()

    result = {
        "raw": raw,
        "period_type": None,
        "fy_label": None,
        "quarter": None,
    }

    q_match = re.search(r"Q([1-4])", raw, re.I)

    if q_match:
        result["quarter"] = f"Q{q_match.group(1)}"
        result["period_type"] = "quarter"

    for pat in _FY_PATTERNS:
        m = pat.search(raw)

        if m:
            groups = m.groups()

            # "FY2024-25" and "FY25" both normalize to FY25.
            year = (
                groups[-1]
                if len(groups) > 1 and groups[-1]
                else groups[0]
            )

            year_short = (
                year[-2:]
                if len(year) == 4
                else year.zfill(2)
            )

            result["fy_label"] = f"FY{year_short}"

            if result["period_type"] is None:
                result["period_type"] = "FY"

            break

    if result["period_type"] is None:
        if re.search(r"\bfull.?year\b", raw, re.I):
            result["period_type"] = "FY"
        elif re.search(
            r"\bmonth\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
            raw,
            re.I,
        ):
            result["period_type"] = "month"

    return result


def periods_comparable(
    period_a: dict,
    period_b: dict,
) -> tuple[bool, str]:
    """
    Determine whether two normalized textual periods represent
    the same reporting window.
    """

    if (
        period_a["fy_label"]
        and period_b["fy_label"]
        and period_a["fy_label"] != period_b["fy_label"]
    ):
        return False, "DIFFERENT_PERIOD"

    if period_a["quarter"] != period_b["quarter"]:
        return False, "DIFFERENT_PERIOD"

    return True, "SAME_PERIOD"
