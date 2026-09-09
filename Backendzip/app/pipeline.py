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
        # 7. LINK NEW CLAIMS
        # ====================================================

        link_new_claims(
            session_id,
            new_claim_ids,
        )

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


def link_new_claims(session_id, new_claim_ids):
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in new_claim_ids)

        new_rows = conn.execute(
            f"""
            SELECT *
            FROM claims
            WHERE id IN ({placeholders})
              AND verified = 1
            """,
            tuple(new_claim_ids),
        ).fetchall()

        if not new_rows:
            return

        existing_rows = conn.execute(
            """
            SELECT claims.*
            FROM claims
            JOIN documents
              ON documents.id = claims.document_id
            WHERE documents.session_id = ?
              AND claims.verified = 1
              AND claims.id NOT IN (
                  SELECT id
                  FROM claims
                  WHERE id IN ({})
              )
            """.format(placeholders),
            (session_id, *new_claim_ids),
        ).fetchall()

        if not existing_rows:
            return

        new_claims = [dict(row) for row in new_rows]
        existing_claims = [dict(row) for row in existing_rows]

        # ---------------------------------------------------------
        # 1. Generate candidate pairs
        # ---------------------------------------------------------

        pairs = []

        for claim in new_claims:
            candidates = find_candidates(
                claim,
                existing_claims,
            )

            for other in candidates:
                pairs.append((claim, other))

        if not pairs:
            print("No candidate relationships found.")
            return

        print(
            f"Candidate relationship pairs: {len(pairs)}"
        )

        # ---------------------------------------------------------
        # 2. Deterministic evaluation first
        # ---------------------------------------------------------

        deterministic_results, llm_pairs = evaluate_pairs(
            pairs
        )

        print(
            f"Deterministic relationships: "
            f"{len(deterministic_results)}"
        )

        print(
            f"LLM relationships required: "
            f"{len(llm_pairs)}"
        )

        # ---------------------------------------------------------
        # 3. Store deterministic results in memory
        # ---------------------------------------------------------

        relationships = list(
            deterministic_results
        )

        # ---------------------------------------------------------
        # 4. Batch ambiguous pairs through Gemini
        # ---------------------------------------------------------

        if llm_pairs:
            llm_results, total_tokens = (
                _run_relationship_judgment(
                    llm_pairs
                )
            )

            print("[DEBUG] First LLM relationship result:")
            print(
                llm_results[0]
                if llm_results
                else "NO RESULTS"
            )

            print(
                f"LLM relationship judgments: "
                f"{len(llm_results)}"
            )

            print(
                f"LLM relationship tokens: "
                f"{total_tokens}"
            )

            relationships.extend(
                llm_results
            )

        # ---------------------------------------------------------
        # 5. Store all relationships
        # ---------------------------------------------------------

        now = datetime.now(
            timezone.utc
        ).isoformat()

        for relationship in relationships:
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
                    relationship[
                        "source_claim_id"
                    ],
                    relationship[
                        "target_claim_id"
                    ],
                    relationship[
                        "relationship_type"
                    ],
                    relationship[
                        "reason_code"
                    ],
                    relationship[
                        "explanation"
                    ],
                    relationship.get(
                        "confidence"
                    ),
                    relationship.get(
                        "decided_by",
                        "rule",
                    ),
                    now,
                ),
            )

        conn.commit()

        print(
            f"Stored {len(relationships)} relationships."
        )