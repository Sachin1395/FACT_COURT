"""
Every LLM call in this system goes through this file.

Entry points:
    extract_claims(evidence_block) -> list[ExtractedClaimRaw]
    judge_relationship(claim_a, claim_b) -> Relationship verdict

Batch entry points:
    extract_claims_batch(evidence_blocks)
    judge_relationships_batch(pairs)

Uses Google Gemini 3.1 Flash-Lite with:
- token-aware batching
- RPM limiting
- TPM limiting
- RPD limiting
- token estimation
- actual token tracking
- exponential backoff
- structured JSON output
"""

import asyncio
import json
import os
import threading
import time
from typing import Any

from google import genai
from google.genai import types

from app.models.schemas import ExtractedClaimRaw


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "gemini-3.1-flash-lite"

MAX_RPM = 15
MAX_TPM = 250_000
MAX_RPD = 500

MAX_BATCH_BLOCKS = 20
MAX_BATCH_TOKENS = 12_000

MAX_PAIR_BATCH = 10
MAX_PAIR_BATCH_TOKENS = 12_000

MAX_RETRIES = 4
INITIAL_RETRY_DELAY = 5

REQUEST_DELAY = 0.1


# ============================================================
# GEMINI CLIENT
# ============================================================

def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return None

    return genai.Client(api_key=api_key)


# ============================================================
# TOKEN ESTIMATION
# ============================================================

def _estimate_tokens(text: str) -> int:
    """
    Conservative token estimate.

    Approximately 4 characters ~= 1 token.
    Used for batching and pre-flight TPM protection.
    """

    if not text:
        return 0

    return max(1, (len(text) + 3) // 4)


def _estimate_request_tokens(
    prompt: str,
    system_prompt: str,
) -> int:
    return (
        _estimate_tokens(prompt)
        + _estimate_tokens(system_prompt)
    )


# ============================================================
# RATE LIMITER
# ============================================================

class AsyncTokenBucketLimiter:
    def __init__(
        self,
        max_rpm=MAX_RPM,
        max_tpm=MAX_TPM,
        max_rpd=MAX_RPD,
    ):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_rpd = max_rpd

        self.request_times = []
        self.token_events = []
        self.day_start = time.time()
        self.daily_requests = 0

        self._lock = threading.Lock()

    def _reset_day_if_needed(self):
        now = time.time()

        if now - self.day_start >= 86400:
            self.day_start = now
            self.daily_requests = 0

    def _cleanup(self):
        now = time.time()

        self.request_times = [
            timestamp
            for timestamp in self.request_times
            if now - timestamp < 60
        ]

        self.token_events = [
            (timestamp, tokens)
            for timestamp, tokens in self.token_events
            if now - timestamp < 60
        ]

    async def wait_for_permits(self, estimated_tokens):
        while True:
            wait_time = 0

            with self._lock:
                self._reset_day_if_needed()
                self._cleanup()

                if self.daily_requests >= self.max_rpd:
                    raise RuntimeError(
                        "Gemini daily request limit reached."
                    )

                now = time.time()

                request_count = len(self.request_times)
                token_count = sum(
                    tokens
                    for _, tokens in self.token_events
                )

                if request_count >= self.max_rpm:
                    oldest = min(self.request_times)
                    wait_time = max(
                        wait_time,
                        60 - (now - oldest),
                    )

                if (
                    self.token_events
                    and token_count + estimated_tokens > self.max_tpm
                ):
                    oldest_token_time = min(
                        timestamp
                        for timestamp, _ in self.token_events
                    )

                    wait_time = max(
                        wait_time,
                        60 - (now - oldest_token_time),
                    )

                if wait_time <= 0:
                    now = time.time()

                    self.request_times.append(now)
                    self.token_events.append(
                        (now, estimated_tokens)
                    )
                    self.daily_requests += 1

                    return

            await asyncio.sleep(
                max(wait_time, 0.1)
            )


_limiter = AsyncTokenBucketLimiter()

EXTRACTION_SYSTEM_PROMPT = """
You are an expert data extractor, specializing in financial and economic documents.
Your task is to extract structured factual claims from provided evidence blocks.

An evidence block contains:
- block_id
- page
- text

Crucially, the **evidence_quote** you provide must be verified against the source
text. Therefore, you must NOT paraphrase, summarize, or alter the wording of the
source. Your extraction must be a verbatim substring that forms a complete,
standalone factual proposition.

==================================================
WHAT COUNTS AS A VALID CLAIM (VERBATIM)
==================================================

A valid claim must be a COMPLETE, STANDALONE FACTUAL PROPOSITION.
It must form a coherent sentence when read aloud.

**You must extract a continuous span of text from the source that requires no
alteration to be understood.**

It should normally contain enough context to answer:
- WHO or WHAT is being discussed (Subject/Entity)?
- WHAT happened/changed/was measured (Predicate/Metric)?
- WHAT is the relevant value, state, or event (Magnitude)?

Good examples (must be found verbatim in source):
- "India's international reserves increased from $646.4 billion at end-FY2023/24
  to $668.3 billion at end-FY2024/25."
- "The current account deficit declined to 0.6 percent of GDP in FY2024/25
  from 0.7 percent of GDP in the previous year."

==================================================
STRICT NEGATIVE CONSTRAINTS
==================================================

DO NOT extract claims if:

1. **You have to change or add words** to make it a complete sentence.
2. **It is a summary** of the surrounding text rather than a direct quote.
3. **It is a fragment** (e.g., continuation phrases like "to $668.3 billion" or
   parenthetical asides like "(from 0.7% of GDP)").
4. **It is a list or table-row artifact** (e.g., "Tomato | 67% | Rabi").
5. **It is merely labels and numbers juxtaposed** (e.g., "Inflation 4%"). It must
   have a verbal predicate (e.g., "Inflation reached 4%").
6. **It requires pronouns** (it, they, this) whose antecedents are outside the
   extracted quote.

==================================================
QUALITY TEST & VERIFICATION COMPATIBILITY
==================================================

Before finalizing a claim, simulate the verification step:
Imagine normalizing both the source text and your extracted quote (removing
punctuation, lowercasing, normalizing whitespace).

Ask yourself: **Is the text of my claim essentially an exact match to a substring
of the source text (allowing for minor tokenization differences)?**

If the answer is NO—if you have rephrased the concept or combined non-adjacent
fragments—Gemini will likely fail the verification step. You must prefer FEWER
high-quality verbatim claims over MANY summarized claims.

==================================================
FACTUALITY RULES
==================================================

Extract claims that state specific numbers, percentages, measurable metrics,
date-bound events, or material changes. Skip narrative filler, opinions, vague
statements, and forward-looking statements without a stated figure.

Never invent information or infer periods/units not explicitly stated in the
verbatim quote.

==================================================
EVIDENCE RULES (CRITICAL)
==================================================

evidence_quote MUST be an exact substring of the corresponding evidence block's
text, copied character-for-character.

Do not paraphrase or alter the wording of the evidence_quote.

block_id MUST identify the evidence block from which the claim was extracted.

Capture period_start, period_end, period_type, scope, basis, and definition
only when explicitly stated *within* the verbatim quote.

Return only JSON matching the supplied response schema.
"""

ADJUDICATION_SYSTEM_PROMPT = """
You are the relationship adjudicator for an evidence-first fact intelligence system.
Your task is to determine the relationship between TWO extracted claims.

You MUST first determine whether the claims describe the SAME underlying
metric or fact. Only then should you determine whether they corroborate,
contradict, reconcile, or remain uncertain.

==================================================
STEP 1 — SAME UNDERLYING METRIC
==================================================

Compare: subject, entity, predicate, value type, unit, period, scope, basis,
definition, and evidence context.

A relationship is valid only if the claims refer to the same underlying
metric, fact, or directly comparable measurement.

DO NOT create relationships merely because claims share the same company,
country, industry, or broad economic topic.

The following are DIFFERENT metrics. If encountered, return UNCERTAIN / INSUFFICIENT_CONTEXT:
- cash balance vs cash flow from operations
- GDP growth vs inflation
- inflation vs PMI
- revenue vs EBITDA

Do NOT classify unrelated metrics as RECONCILES.

==================================================
STEP 2 — CONTEXT AND RELATIONSHIP DEFINITIONS
==================================================

If the claims describe the same underlying metric, compare their context.

CORROBORATES
Use when the claims describe the SAME underlying metric and their values are
consistent (e.g., EXACT_MATCH, UNIT_NORMALIZATION, ROUNDING).

RECONCILES
Use when the SAME underlying metric/fact is being measured but the difference
in values is explained by a legitimate contextual distinction.

Valid reasons:
- DIFFERENT_PERIOD
- DIFFERENT_SCOPE
- DIFFERENT_DEFINITION
- ESTIMATE_VINTAGE
- METHODOLOGY_CHANGE

CRITICAL RULE ON PERIODS:
Different reporting periods do NOT override the same-metric rule. If two claims
represent the same underlying measurement (e.g., Revenue) but report different
periods (e.g., Q1 vs Q2, or Annual vs Quarterly), they must be classified as:
RECONCILES / DIFFERENT_PERIOD.
Do not classify these as CONTRADICTS.

CONTRADICTS
Use CONTRADICTS only when:
1. The claims describe the SAME underlying metric.
2. They refer to substantially the SAME period.
3. They refer to substantially the SAME scope.
4. Their definitions, basis, and methodology are compatible.
5. There is no estimate-vintage or other contextual explanation.
6. The values materially conflict (they cannot both be true).

UNCERTAIN
Use UNCERTAIN when:
- the claims describe different metrics
- the underlying metric cannot be established confidently
- critical evidence is missing or ambiguous
- entity identity is unclear
- the available evidence does not allow reliable classification

==================================================
DECISION ORDER
==================================================

Follow this strict order:
1. Different metrics or underlying facts?
   → UNCERTAIN / INSUFFICIENT_CONTEXT
2. Same metric + materially conflicting values (no context diff)?
   → CONTRADICTS / NUMERIC_DISCREPANCY
3. Same metric + equivalent values (rounding/units)?
   → CORROBORATES
4. Same metric + contextual difference explains discrepancy (period/scope/etc.)?
   → RECONCILES with appropriate reason_code
5. Insufficient evidence to determine context/metrics?
   → UNCERTAIN / INSUFFICIENT_CONTEXT

==================================================
EVIDENCE-FIRST REQUIREMENT
==================================================

Base the decision only on the supplied claim fields and evidence. Do not invent
facts, periods, scopes, or methodologies.

==================================================
OUTPUT
==================================================

For a SINGLE claim pair, return ONLY valid JSON matching the response schema.

relationship_type MUST be exactly one of:
- CORROBORATES
- CONTRADICTS
- RECONCILES
- UNCERTAIN

reason_code MUST be exactly one of:
- EXACT_MATCH
- UNIT_NORMALIZATION
- ROUNDING
- DIFFERENT_PERIOD
- DIFFERENT_SCOPE
- DIFFERENT_DEFINITION
- ESTIMATE_VINTAGE
- METHODOLOGY_CHANGE
- ENTITY_MISMATCH
- NUMERIC_DISCREPANCY
- INSUFFICIENT_CONTEXT

The explanation MUST be one or two sentences identifying the specific
evidence field or contextual difference that determined the result.
"""


BATCH_ADJUDICATION_SUFFIX = """
BATCH OUTPUT CONTRACT

Judge every claim pair independently.

Return ONLY one JSON object. The top-level keys MUST be exactly the supplied
pair_id values. Each pair_id MUST map to exactly one verdict object containing:
relationship_type, reason_code, explanation, confidence.

Do not return a JSON array. Do not omit any pair_id. Do not add commentary
outside the JSON object.

RECONCILES vs CONTRADICTS REMINDER:
Claims regarding the same metric (e.g., "Revenue") but for different periods
(e.g., "FY2023" vs "FY2024") do NOT contradict. They are different facts
about the same topic. You must return:
RECONCILES / DIFFERENT_PERIOD.
"""
# ============================================================
# ERROR HELPERS
# ============================================================

def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()

    return (
        "429" in message
        or "resource_exhausted" in message
        or "rate limit" in message
        or "quota exceeded" in message
    )


def _retry_delay(attempt: int) -> float:
    return INITIAL_RETRY_DELAY * (2 ** attempt)


# ============================================================
# LOW LEVEL GEMINI REQUEST
# ============================================================

async def _async_generate(
    prompt: str,
    system_prompt: str,
    response_schema: Any = None,
) -> tuple[str, int]:

    client = _get_client()

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY is not set."
        )

    estimated_tokens = _estimate_request_tokens(
        prompt,
        system_prompt,
    )

    print(
        "[Metrics] Estimated input tokens: "
        f"{estimated_tokens:,}"
    )

    await _limiter.wait_for_permits(
        estimated_tokens
    )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0,
        response_mime_type="application/json",
    )

    if response_schema is not None:
        config.response_schema = response_schema

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

            actual_tokens = estimated_tokens

            if response.usage_metadata:
                actual_tokens = (
                    getattr(
                        response.usage_metadata,
                        "total_token_count",
                        None,
                    )
                    or getattr(
                        response.usage_metadata,
                        "prompt_token_count",
                        None,
                    )
                    or estimated_tokens
                )

            print(
                "[Metrics] Actual tokens consumed: "
                f"{actual_tokens:,}"
            )

            return (
                (response.text or "").strip(),
                actual_tokens,
            )

        except Exception as error:
            if not _is_rate_limit_error(error):
                raise

            if attempt >= MAX_RETRIES - 1:
                raise

            delay = _retry_delay(attempt)

            print(
                "[Gemini] Rate limit/quota error. "
                f"Retrying in {delay}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )

            await asyncio.sleep(delay)

    raise RuntimeError(
        "Gemini request failed after retries."
    )


# ============================================================
# CLAIM EXTRACTION
# ============================================================

async def _extract_claims_async(
    block_text: str,
) -> tuple[list[ExtractedClaimRaw], int]:

    try:
        raw, tokens = await _async_generate(
            prompt=block_text,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            response_schema=list[ExtractedClaimRaw],
        )

        items = json.loads(raw)

        if not isinstance(items, list):
            return [], tokens

        claims = []

        for item in items:
            try:
                claims.append(
                    ExtractedClaimRaw(**item)
                )
            except Exception as error:
                print(
                    "[Gemini] Invalid claim skipped: "
                    f"{error}"
                )

        return claims, tokens

    except Exception as error:
        print(
            "[Gemini] Claim extraction failed: "
            f"{error}"
        )

        return [], 0


def _build_token_aware_batches(
    evidence_blocks: list[dict],
    batch_size: int = MAX_BATCH_BLOCKS,
    max_tokens: int = MAX_BATCH_TOKENS,
) -> list[list[dict]]:

    if not evidence_blocks:
        return []

    batches = []
    current_batch = []
    system_tokens = _estimate_tokens(
        EXTRACTION_SYSTEM_PROMPT
    )
    current_tokens = system_tokens

    for block in evidence_blocks:
        formatted_block = f"""
<EVIDENCE_BLOCK>
<block_id>{block["id"]}</block_id>
<page>{block["page"]}</page>
<text>
{block["text"]}
</text>
</EVIDENCE_BLOCK>
"""

        block_tokens = _estimate_tokens(
            formatted_block
        )

        if block_tokens + system_tokens > max_tokens:
            print(
                "[Batching] Warning: evidence block "
                f"{block['id']} exceeds the configured "
                f"batch token budget ({max_tokens:,}). "
                "Sending it as a standalone request."
            )

            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = system_tokens

            batches.append([block])
            continue

        would_exceed_tokens = (
            current_tokens + block_tokens > max_tokens
        )

        would_exceed_blocks = (
            len(current_batch) >= batch_size
        )

        if current_batch and (
            would_exceed_tokens
            or would_exceed_blocks
        ):
            batches.append(current_batch)
            current_batch = []
            current_tokens = system_tokens

        current_batch.append(block)
        current_tokens += block_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


async def _extract_claims_batch_async(
    evidence_blocks: list[dict],
) -> tuple[list[ExtractedClaimRaw], int]:

    if not evidence_blocks:
        return [], 0

    formatted_blocks = []

    for block in evidence_blocks:
        formatted_blocks.append(
            f"""
<EVIDENCE_BLOCK>
<block_id>{block["id"]}</block_id>
<page>{block["page"]}</page>
<text>
{block["text"]}
</text>
</EVIDENCE_BLOCK>
"""
        )

    prompt = "\n".join(formatted_blocks)

    try:
        raw, tokens = await _async_generate(
            prompt=prompt,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            response_schema=list[ExtractedClaimRaw],
        )

        items = json.loads(raw)

        if not isinstance(items, list):
            return [], tokens

        claims = []

        for item in items:
            try:
                claims.append(
                    ExtractedClaimRaw(**item)
                )
            except Exception as error:
                print(
                    "[Gemini] Invalid batched claim skipped: "
                    f"{error}"
                )

        return claims, tokens

    except Exception as error:
        print(
            "[Gemini] Batch extraction failed: "
            f"{error}"
        )

        return [], 0


async def extract_claims_batch(
    evidence_blocks: list[dict],
    batch_size: int = MAX_BATCH_BLOCKS,
    max_tokens: int = MAX_BATCH_TOKENS,
) -> tuple[list[ExtractedClaimRaw], int]:

    if not evidence_blocks:
        return [], 0

    batches = _build_token_aware_batches(
        evidence_blocks,
        batch_size=batch_size,
        max_tokens=max_tokens,
    )

    print(
        "[Batching] "
        f"{len(evidence_blocks)} evidence blocks "
        f"→ {len(batches)} Gemini requests"
    )

    all_claims = []
    total_tokens = 0

    for index, batch in enumerate(batches, start=1):
        print(
            f"[Gemini] Extraction batch "
            f"{index}/{len(batches)} | "
            f"blocks={len(batch)}"
        )

        claims, tokens = await _extract_claims_batch_async(
            batch
        )

        all_claims.extend(claims)
        total_tokens += tokens

        if index < len(batches):
            await asyncio.sleep(REQUEST_DELAY)

    print(
        "[Metrics] Total extraction tokens: "
        f"{total_tokens:,}"
    )

    return all_claims, total_tokens


# ============================================================
# SINGLE RELATIONSHIP ADJUDICATION
# ============================================================

async def _judge_relationship_async(
    claim_a: dict,
    claim_b: dict,
) -> tuple[dict, int]:

    payload = json.dumps(
        {
            "claim_a": claim_a,
            "claim_b": claim_b,
        },
        default=str,
    )

    try:
        raw, tokens = await _async_generate(
            prompt=payload,
            system_prompt=ADJUDICATION_SYSTEM_PROMPT,
        )

        result = json.loads(raw)

        if not isinstance(result, dict):
            raise ValueError(
                "Gemini relationship output "
                "is not a JSON object."
            )

        return result, tokens

    except Exception as error:
        print(
            "[Gemini] Relationship adjudication failed: "
            f"{error}"
        )

        return {
            "relationship_type": "UNCERTAIN",
            "reason_code": "INSUFFICIENT_CONTEXT",
            "explanation": (
                "Gemini returned invalid or unusable output."
            ),
            "confidence": 0.0,
        }, 0


# ============================================================
# BATCH RELATIONSHIP ADJUDICATION
# ============================================================

def _format_claim_for_adjudication(claim: dict) -> dict:
    return {
        "id": claim.get("id"),
        "subject": claim.get("subject"),
        "predicate": claim.get("predicate"),
        "value": claim.get("value"),
        "value_type": claim.get("value_type"),
        "unit": claim.get("unit"),
        "period_start": claim.get("period_start"),
        "period_end": claim.get("period_end"),
        "period_type": claim.get("period_type"),
        "scope": claim.get("scope"),
        "basis": claim.get("basis"),
        "definition": claim.get("definition"),
        "claim_type": claim.get("claim_type"),
        "source_page": claim.get("source_page"),
        "source_text": claim.get("source_text"),
    }


def _format_relationship_pair(
    pair_id: str,
    claim_a: dict,
    claim_b: dict,
) -> str:

    claim_a_clean = _format_claim_for_adjudication(
        claim_a
    )

    claim_b_clean = _format_claim_for_adjudication(
        claim_b
    )

    return f"""
<CLAIM_PAIR>
<pair_id>{pair_id}</pair_id>

<CLAIM_A>
{json.dumps(claim_a_clean, default=str)}
</CLAIM_A>

<CLAIM_B>
{json.dumps(claim_b_clean, default=str)}
</CLAIM_B>

</CLAIM_PAIR>
""".strip()


def _build_relationship_batches(
    pairs: list[tuple[dict, dict]],
    max_pairs: int = MAX_PAIR_BATCH,
    max_tokens: int = MAX_PAIR_BATCH_TOKENS,
) -> list[list[dict]]:

    if not pairs:
        return []

    batches = []
    current_batch = []
    system_tokens = _estimate_tokens(
        ADJUDICATION_SYSTEM_PROMPT
        + BATCH_ADJUDICATION_SUFFIX
    )
    current_tokens = system_tokens

    for index, (claim_a, claim_b) in enumerate(pairs):
        pair_id = f"pair_{index}"

        formatted = _format_relationship_pair(
            pair_id,
            claim_a,
            claim_b,
        )

        pair_tokens = _estimate_tokens(formatted)

        if pair_tokens + system_tokens > max_tokens:
            print(
                "[Batching] Warning: relationship pair "
                f"{pair_id} exceeds the configured "
                f"batch token budget ({max_tokens:,}). "
                "Sending it as a standalone request."
            )

            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = system_tokens

            batches.append(
                [
                    {
                        "pair_id": pair_id,
                        "claim_a": claim_a,
                        "claim_b": claim_b,
                    }
                ]
            )
            continue

        would_exceed_tokens = (
            current_tokens + pair_tokens > max_tokens
        )

        would_exceed_pairs = (
            len(current_batch) >= max_pairs
        )

        if current_batch and (
            would_exceed_tokens
            or would_exceed_pairs
        ):
            batches.append(current_batch)
            current_batch = []
            current_tokens = system_tokens

        current_batch.append(
            {
                "pair_id": pair_id,
                "claim_a": claim_a,
                "claim_b": claim_b,
            }
        )

        current_tokens += pair_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


async def _judge_relationship_batch_async(
    batch: list[dict],
) -> tuple[dict[str, dict], int]:

    if not batch:
        return {}, 0

    prompt = "\n\n".join(
        _format_relationship_pair(
            item["pair_id"],
            item["claim_a"],
            item["claim_b"],
        )
        for item in batch
    )

    system_prompt = (
        ADJUDICATION_SYSTEM_PROMPT
        + "\n\n"
        + BATCH_ADJUDICATION_SUFFIX
    )

    try:
        raw, tokens = await _async_generate(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        result = json.loads(raw)

        if not isinstance(result, dict):
            raise ValueError(
                "Batched relationship output "
                "is not a JSON object."
            )

        expected_ids = {
            item["pair_id"]
            for item in batch
        }

        returned_ids = set(result.keys())

        if returned_ids != expected_ids:
            raise ValueError(
                "Batched Gemini response contains missing or unexpected pair IDs."
            )

        cleaned = {}

        for pair_id in expected_ids:
            verdict = result[pair_id]

            if isinstance(verdict, dict):
                cleaned[pair_id] = verdict
            else:
                cleaned[pair_id] = {
                    "relationship_type": "UNCERTAIN",
                    "reason_code": "INSUFFICIENT_CONTEXT",
                    "explanation": (
                        "No valid verdict was returned "
                        "for this claim pair."
                    ),
                    "confidence": 0.0,
                }

        return cleaned, tokens

    except Exception as error:
        print(
            "[Gemini] Batched relationship adjudication failed: "
            f"{error}"
        )

        fallback = {}

        for item in batch:
            fallback[item["pair_id"]] = {
                "relationship_type": "UNCERTAIN",
                "reason_code": "INSUFFICIENT_CONTEXT",
                "explanation": (
                    "Batched Gemini adjudication "
                    "failed or returned invalid JSON."
                ),
                "confidence": 0.0,
            }

        return fallback, 0


async def judge_relationships_batch(
    pairs: list[tuple[dict, dict]],
    max_pairs: int = MAX_PAIR_BATCH,
    max_tokens: int = MAX_PAIR_BATCH_TOKENS,
) -> tuple[list[dict], int]:

    if not pairs:
        return [], 0

    batches = _build_relationship_batches(
        pairs,
        max_pairs=max_pairs,
        max_tokens=max_tokens,
    )

    print(
        "[Batching] Relationship adjudication: "
        f"{len(pairs)} pairs -> "
        f"{len(batches)} Gemini requests"
    )

    all_judgments = []
    total_tokens = 0

    for index, batch in enumerate(batches, start=1):
        print(
            f"[Gemini] Relationship batch "
            f"{index}/{len(batches)} | "
            f"pairs={len(batch)}"
        )

        results, tokens = await _judge_relationship_batch_async(
            batch
        )

        for item in batch:
            pair_id = item["pair_id"]
            verdict = results.get(pair_id)

            if not isinstance(verdict, dict):
                verdict = {
                    "relationship_type": "UNCERTAIN",
                    "reason_code": "INSUFFICIENT_CONTEXT",
                    "explanation": (
                        "No valid verdict was returned "
                        "for this claim pair."
                    ),
                    "confidence": 0.0,
                }

            all_judgments.append(
                {
                    "source_claim_id": item["claim_a"]["id"],
                    "target_claim_id": item["claim_b"]["id"],
                    "relationship_type": verdict.get(
                        "relationship_type",
                        "UNCERTAIN",
                    ),
                    "reason_code": verdict.get(
                        "reason_code",
                        "INSUFFICIENT_CONTEXT",
                    ),
                    "explanation": verdict.get(
                        "explanation",
                        "No explanation was returned.",
                    ),
                    "confidence": verdict.get(
                        "confidence",
                        0.0,
                    ),
                    "decided_by": "llm",
                }
            )

        total_tokens += tokens

        if index < len(batches):
            await asyncio.sleep(REQUEST_DELAY)

    print(
        "[Metrics] Total relationship "
        f"adjudication tokens: {total_tokens:,}"
    )

    return all_judgments, total_tokens


# ============================================================
# SYNCHRONOUS ASYNC RUNNER
# ============================================================

def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    raise RuntimeError(
        "Synchronous LLM entry point was called from an "
        "active asyncio event loop. Use the async API instead."
    )


# ============================================================
# SYNCHRONOUS PUBLIC APIs
# ============================================================

def extract_claims(
    evidence_block: str,
) -> list[ExtractedClaimRaw]:

    if _get_client() is None:
        return []

    result, tokens = _run_async(
        _extract_claims_async(evidence_block)
    )

    print(
        "[Metrics] Extraction tokens consumed: "
        f"{tokens:,}"
    )

    return result


def judge_relationship(
    claim_a: dict,
    claim_b: dict,
) -> dict:

    if _get_client() is None:
        return {
            "relationship_type": "UNCERTAIN",
            "reason_code": "INSUFFICIENT_CONTEXT",
            "explanation": "Gemini adjudicator unavailable.",
            "confidence": 0.0,
        }

    result, tokens = _run_async(
        _judge_relationship_async(
            claim_a,
            claim_b,
        )
    )

    print(
        "[Metrics] Adjudication tokens consumed: "
        f"{tokens:,}"
    )

    return result
