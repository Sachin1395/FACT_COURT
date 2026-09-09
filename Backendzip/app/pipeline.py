import uuid
from datetime import datetime, timezone

import re
from difflib import SequenceMatcher
from app.db.database import get_conn
from app.extraction.pdf_extract import extract_evidence_blocks
from app.reasoning.llm import extract_claims_batch
from app.matching.candidates import find_candidates

from app.reasoning.relationships import evaluate_pairs
from app.reasoning.llm import judge_relationships_batch


def process_document(
    pdf_path: str,
    document_id: str,
    session_id: str,
):
    """
    Process one PDF inside a specific analysis session.

    Flow:

        PDF
        ↓
        Evidence blocks
        ↓
        Token-aware Gemini batches
        ↓
        Claim extraction
        ↓
        Evidence verification
        ↓
        SQLite
        ↓
        Compare new claims against existing claims
        in the SAME session
    """

    try:

        # ====================================================
        # 1. EXTRACT EVIDENCE BLOCKS
        # ====================================================

        blocks = extract_evidence_blocks(
            pdf_path,
            document_id,
        )

        # ====================================================
        # 2. STORE EVIDENCE BLOCKS
        # ====================================================

        with get_conn() as conn:

            for block in blocks:

                conn.execute(
                    """
                    INSERT INTO evidence_blocks (
                        id,
                        document_id,
                        page,
                        block_type,
                        text
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        block["id"],
                        block["document_id"],
                        block["page"],
                        block["block_type"],
                        block["text"],
                    ),
                )

            conn.execute(
                """
                UPDATE documents
                SET status = 'parsed'
                WHERE id = ?
                """,
                (document_id,),
            )

        # ====================================================
        # 3. TOKEN-AWARE BATCH CLAIM EXTRACTION
        # ====================================================

        raw_claims, total_tokens = (
            _run_claim_extraction(
                blocks
            )
        )

        print(
            f"[Pipeline] Extracted "
            f"{len(raw_claims)} raw claims "
            f"from {len(blocks)} evidence blocks."
        )

        print(
            f"[Pipeline] Total extraction tokens: "
            f"{total_tokens:,}"
        )

        # ====================================================
        # 4. CREATE BLOCK LOOKUP
        # ====================================================

        blocks_by_id = {
            block["id"]: block
            for block in blocks
        }

        # ====================================================
        # 5. STORE CLAIMS
        # ====================================================

        new_claim_ids = []

        for rc in raw_claims:

            # ----------------------------------------------
            # Find the evidence block Gemini referenced.
            # ----------------------------------------------

            block = blocks_by_id.get(
                rc.block_id
            )

            if block is None:

                print(
                    "[Pipeline] Claim references unknown "
                    f"block_id={rc.block_id}. Skipping."
                )

                continue

            # ----------------------------------------------
            # Verify evidence quote.
            # ----------------------------------------------

            evidence_quote = rc.evidence_quote.strip()
            block_text = block["text"].strip()

            def normalize_text(text: str) -> str:
                """
                Normalize PDF/LLM formatting differences while
                preserving the actual words and numbers.
                """
                text = text.lower()

                # Normalize common Unicode punctuation
                text = text.replace("–", "-")
                text = text.replace("—", "-")
                text = text.replace("−", "-")
                text = text.replace("’", "'")
                text = text.replace("“", '"')
                text = text.replace("”", '"')

                # Normalize whitespace/newlines
                text = re.sub(r"\s+", " ", text)

                return text.strip()

            normalized_quote = normalize_text(evidence_quote)
            normalized_block = normalize_text(block_text)

            verified = False

            if normalized_quote:
                # 1. Exact normalized substring match
                if normalized_quote in normalized_block:
                    verified = True

                else:
                    # 2. Conservative token-based verification
                    #
                    # This handles cases where PDF extraction and
                    # Gemini formatting differ slightly.
                    quote_tokens = normalized_quote.split()
                    block_tokens = normalized_block.split()

                    if len(quote_tokens) >= 4 and len(block_tokens) >= len(quote_tokens):

                        quote_len = len(quote_tokens)

                        best_similarity = 0.0

                        for i in range(
                                len(block_tokens) - quote_len + 1
                        ):
                            candidate_tokens = block_tokens[
                                               i:i + quote_len
                                               ]

                            candidate = " ".join(candidate_tokens)
                            quote = " ".join(quote_tokens)

                            similarity = SequenceMatcher(
                                None,
                                quote,
                                candidate,
                            ).ratio()

                            best_similarity = max(
                                best_similarity,
                                similarity,
                            )

                        # High threshold deliberately used so that
                        # weak/incorrect evidence is not accepted.
                        if best_similarity >= 0.92:
                            verified = True

            if not verified:
                print(
                    "[Pipeline] Evidence verification failed "
                    f"for block {rc.block_id}"
                )
            claim_id = str(uuid.uuid4())

            # ----------------------------------------------
            # Store claim.
            # ----------------------------------------------

            with get_conn() as conn:

                conn.execute(
                    """
                    INSERT INTO claims (
                        id,
                        document_id,
                        evidence_block_id,
                        subject,
                        predicate,
                        value,
                        value_type,
                        unit,
                        period_start,
                        period_end,
                        period_type,
                        scope,
                        basis,
                        definition,
                        claim_type,
                        source_page,
                        source_text,
                        verified,
                        confidence,
                        created_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        claim_id,
                        document_id,
                        block["id"],
                        rc.subject,
                        rc.predicate,
                        rc.value,
                        rc.value_type,
                        rc.unit,
                        rc.period_start,
                        rc.period_end,
                        rc.period_type,
                        rc.scope,
                        rc.basis,
                        rc.definition,
                        rc.claim_type,
                        block["page"],
                        rc.evidence_quote,
                        int(verified),
                        rc.confidence,
                        datetime.now(
                            timezone.utc
                        ).isoformat(),
                    ),
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO predicate_registry (
                        predicate,
                        first_seen_document_id,
                        example_definition
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        rc.predicate,
                        document_id,
                        rc.definition,
                    ),
                )

            new_claim_ids.append(
                claim_id
            )

        # ====================================================
        # 6. MARK DOCUMENT EXTRACTED
        # ====================================================

        with get_conn() as conn:

            conn.execute(
                """
                UPDATE documents
                SET status = 'extracted'
                WHERE id = ?
                """,
                (document_id,),
            )


        # ====================================================
        # 7. RELATIONSHIPS ARE LINKED AFTER ALL DOCUMENTS
        #    IN THE UPLOAD BATCH HAVE BEEN PROCESSED.
        #
        #    Do not compare here. When multiple PDFs are uploaded
        #    together, FastAPI background tasks can otherwise finish
        #    in an unpredictable order and some documents may see
        #    only a partial set of claims.
        # ====================================================

    except Exception as error:

        print(
            f"[Pipeline] Document processing failed: "
            f"{error}"
        )

        with get_conn() as conn:

            conn.execute(
                """
                UPDATE documents
                SET status = 'failed'
                WHERE id = ?
                """,
                (document_id,),
            )

        raise


def process_documents_batch(
    jobs: list[tuple[str, str, str]],
):
    """
    Process a group of uploaded PDFs sequentially.

    Each job is:
        (pdf_path, document_id, session_id)

    Relationships are generated only after every document in the
    batch has finished claim extraction and storage. This makes
    multi-PDF analysis deterministic and ensures every verified
    claim in the session is available to candidate generation.
    """

    if not jobs:
        return

    session_id = jobs[0][2]

    # All jobs in one upload request must belong to the same session.
    for _, _, job_session_id in jobs:
        if job_session_id != session_id:
            raise ValueError(
                "All documents in a processing batch must belong "
                "to the same session."
            )

    print(
        f"[Pipeline] Processing {len(jobs)} document(s) "
        f"sequentially for session {session_id}"
    )

    successful = 0

    for pdf_path, document_id, job_session_id in jobs:
        try:
            process_document(
                pdf_path,
                document_id,
                job_session_id,
            )
            successful += 1
        except Exception as error:
            # process_document already marks the document as failed.
            # Continue processing the remaining PDFs so one bad file
            # does not prevent the rest of the upload batch.
            print(
                f"[Pipeline] Skipping failed document "
                f"{document_id}: {error}"
            )

    print(
        f"[Pipeline] Document batch complete: "
        f"{successful}/{len(jobs)} succeeded."
    )

    # One session-wide relationship pass after ALL documents have
    # been extracted.
    link_session_claims(session_id)


def _run_claim_extraction(
    blocks: list[dict],
):
    """
    Run the async token-aware batch extractor from the
    synchronous document-processing pipeline.
    """

    import asyncio

    return asyncio.run(
        extract_claims_batch(
            blocks
        )
    )


def _run_relationship_judgment(llm_pairs):
    """
    Run the async relationship judge from the
    synchronous document-processing pipeline.
    """

    import asyncio

    return asyncio.run(
        judge_relationships_batch(
            llm_pairs
        )
    )


def _relationship_exists(
    conn,
    claim_a_id: str,
    claim_b_id: str,
) -> bool:
    """
    Relationships are conceptually undirected for duplicate detection.

    A-B and B-A represent the same pair, even though the stored
    relationship keeps a source and target claim ID.
    """

    row = conn.execute(
        """
        SELECT 1
        FROM relationships
        WHERE
            (
                source_claim_id = ?
                AND target_claim_id = ?
            )
            OR
            (
                source_claim_id = ?
                AND target_claim_id = ?
            )
        LIMIT 1
        """,
        (
            claim_a_id,
            claim_b_id,
            claim_b_id,
            claim_a_id,
        ),
    ).fetchone()

    return row is not None


def link_session_claims(session_id: str):
    """
    Compare ALL verified claims in a session.

    This replaces the old "new claims vs existing claims" approach.
    Relationship generation therefore does not depend on which PDF
    happened to finish first.

    Candidate generation remains conservative, while deterministic
    rules and Gemini adjudicate the resulting candidate pairs.
    """

    # ---------------------------------------------------------
    # 1. Load every verified claim in the session.
    # ---------------------------------------------------------

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT claims.*
            FROM claims
            JOIN documents
                ON documents.id = claims.document_id
            WHERE documents.session_id = ?
              AND claims.verified = 1
            ORDER BY claims.created_at ASC
            """,
            (session_id,),
        ).fetchall()

        claims = [
            dict(row)
            for row in rows
        ]

    if len(claims) < 2:
        print(
            "[Relationships] Fewer than 2 verified claims "
            "in session; nothing to compare."
        )
        return

    print(
        f"[Relationships] Session contains "
        f"{len(claims)} verified claims."
    )

    # ---------------------------------------------------------
    # 2. Generate unique candidate pairs across the session.
    # ---------------------------------------------------------

    pairs = []
    seen_pairs = set()

    for index, claim in enumerate(claims):

        # Only compare with claims after this one.
        # This prevents A-B and B-A from both becoming candidates.
        for other in claims[index + 1:]:

            pair_key = tuple(
                sorted(
                    (
                        claim["id"],
                        other["id"],
                    )
                )
            )

            if pair_key in seen_pairs:
                continue

            seen_pairs.add(pair_key)

            candidates = find_candidates(
                claim,
                [other],
            )

            if candidates:
                pairs.append(
                    (
                        claim,
                        other,
                    )
                )

    print(
        f"[Relationships] Candidate relationship pairs: "
        f"{len(pairs)}"
    )

    if not pairs:
        print(
            "[Relationships] No candidate relationships found."
        )
        return

    # ---------------------------------------------------------
    # 3. Remove pairs that already have a stored relationship.
    # ---------------------------------------------------------

    with get_conn() as conn:
        new_pairs = []

        for claim_a, claim_b in pairs:
            if _relationship_exists(
                conn,
                claim_a["id"],
                claim_b["id"],
            ):
                continue

            new_pairs.append(
                (
                    claim_a,
                    claim_b,
                )
            )

    skipped_existing = len(pairs) - len(new_pairs)

    if skipped_existing:
        print(
            f"[Relationships] Skipped "
            f"{skipped_existing} already-stored pairs."
        )

    if not new_pairs:
        print(
            "[Relationships] All candidate pairs already "
            "have stored relationships."
        )
        return

    # ---------------------------------------------------------
    # 4. Deterministic evaluation first.
    # ---------------------------------------------------------

    deterministic_results, llm_pairs = evaluate_pairs(
        new_pairs
    )

    print(
        f"[Relationships] "
        f"{len(new_pairs)} candidate pairs → "
        f"{len(deterministic_results)} deterministic, "
        f"{len(llm_pairs)} require LLM"
    )

    relationships = list(
        deterministic_results
    )

    # ---------------------------------------------------------
    # 5. Batch ambiguous pairs through Gemini.
    # ---------------------------------------------------------

    if llm_pairs:

        llm_results, total_tokens = (
            _run_relationship_judgment(
                llm_pairs
            )
        )

        print(
            "[DEBUG] First LLM relationship result:"
        )

        print(
            llm_results[0]
            if llm_results
            else "NO RESULTS"
        )

        print(
            f"[Relationships] LLM relationship judgments: "
            f"{len(llm_results)}"
        )

        print(
            f"[Relationships] LLM relationship tokens: "
            f"{total_tokens}"
        )

        relationships.extend(
            llm_results
        )

    # ---------------------------------------------------------
    # 6. Store all relationship results.
    # ---------------------------------------------------------

    if not relationships:
        print(
            "[Relationships] No relationship verdicts "
            "were produced."
        )
        return

    now = datetime.now(
        timezone.utc
    ).isoformat()

    stored_count = 0

    with get_conn() as conn:

        for relationship in relationships:

            source_id = relationship.get(
                "source_claim_id"
            )

            target_id = relationship.get(
                "target_claim_id"
            )

            if not source_id or not target_id:
                print(
                    "[Relationships] Skipping malformed "
                    "relationship without claim IDs."
                )
                continue

            # Protect against duplicate results from the current
            # batch as well as relationships already in SQLite.
            if _relationship_exists(
                conn,
                source_id,
                target_id,
            ):
                continue

            conn.execute(
                """
                INSERT INTO relationships (
                    id,
                    source_claim_id,
                    target_claim_id,
                    relationship_type,
                    reason_code,
                    explanation,
                    confidence,
                    decided_by,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    source_id,
                    target_id,
                    relationship.get(
                        "relationship_type",
                        "UNCERTAIN",
                    ),
                    relationship.get(
                        "reason_code",
                        "INSUFFICIENT_CONTEXT",
                    ),
                    relationship.get(
                        "explanation",
                        "No explanation was returned.",
                    ),
                    relationship.get(
                        "confidence"
                    ),
                    relationship.get(
                        "decided_by",
                        "rules",
                    ),
                    now,
                ),
            )

            stored_count += 1

        conn.commit()

    print(
        f"[Relationships] Stored {stored_count} "
        f"new relationships."
    )


# Backwards-compatible wrapper.
#
# Existing callers can still invoke link_new_claims(), but the
# implementation is now session-wide rather than "new vs existing".
def link_new_claims(
    session_id: str,
    new_claim_ids: list[str] | None = None,
):
    """
    Backwards-compatible wrapper for older callers.

    new_claim_ids is intentionally ignored because relationship
    generation is now performed against all verified claims in
    the session.
    """

    link_session_claims(
        session_id
    )
