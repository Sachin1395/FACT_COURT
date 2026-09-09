import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    BackgroundTasks,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.db.database import init_db, get_conn
from app.pipeline import process_document


app = FastAPI(
    title="Superjoin Fact Knowledge Layer"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = (
    Path(__file__).resolve().parent
    / "data"
    / "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    init_db()


# ============================================================
# SESSIONS
# ============================================================

@app.post("/sessions")
def create_session():
    """
    Start a completely new analysis session.

    A session is an isolated workspace containing the PDFs,
    claims, and relationships for one analysis run.
    """

    session_id = str(uuid.uuid4())

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id,
                created_at,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                created_at,
                "active",
            ),
        )

    return {
        "session_id": session_id,
        "status": "active",
    }


@app.get("/sessions")
def list_sessions():
    """
    List all analysis sessions.
    """

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM sessions
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


@app.get("/sessions/{session_id}")
def get_session(
    session_id: str,
):
    """
    Get information about one session.
    """

    with get_conn() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="session not found",
        )

    return dict(row)


# ============================================================
# MULTI-PDF UPLOAD
# ============================================================

@app.post(
    "/sessions/{session_id}/documents"
)
async def upload_documents(
    session_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    """
    Upload multiple PDFs into one session.

    Every uploaded document belongs to this session.
    """

    # --------------------------------------------------------
    # Verify session exists
    # --------------------------------------------------------

    with get_conn() as conn:

        session = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="session not found",
        )

    if session["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="session is not active",
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="no files supplied",
        )

    uploaded = []

    # --------------------------------------------------------
    # Process every uploaded PDF
    # --------------------------------------------------------

    for file in files:

        filename = file.filename or "unknown.pdf"

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"{filename} is not a PDF",
            )

        document_id = str(
            uuid.uuid4()
        )

        dest = (
            UPLOAD_DIR
            / f"{document_id}.pdf"
        )

        # ----------------------------------------------------
        # Save PDF
        # ----------------------------------------------------

        with dest.open("wb") as output_file:
            shutil.copyfileobj(
                file.file,
                output_file,
            )

        # ----------------------------------------------------
        # Insert document
        # ----------------------------------------------------

        uploaded_at = datetime.now(
            timezone.utc
        ).isoformat()

        with get_conn() as conn:

            conn.execute(
                """
                INSERT INTO documents (
                    id,
                    session_id,
                    filename,
                    uploaded_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    session_id,
                    filename,
                    uploaded_at,
                    "pending",
                ),
            )

        # ----------------------------------------------------
        # Queue document processing
        # ----------------------------------------------------

        background_tasks.add_task(
            process_document,
            str(dest),
            document_id,
            session_id,
        )

        uploaded.append(
            {
                "document_id": document_id,
                "filename": filename,
                "status": "processing",
            }
        )

    return {
        "session_id": session_id,
        "status": "processing",
        "documents": uploaded,
    }


# ============================================================
# DOCUMENTS
# ============================================================

@app.get(
    "/sessions/{session_id}/documents"
)
def list_documents(
    session_id: str,
):
    """
    List documents belonging only to this session.
    """

    with get_conn() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE session_id = ?
            ORDER BY uploaded_at DESC
            """,
            (session_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# CLAIMS
# ============================================================

@app.get(
    "/sessions/{session_id}/claims"
)
def list_claims(
    session_id: str,
    document_id: str | None = None,
    verified_only: bool = False,
):
    """
    List claims belonging only to this session.
    """

    query = """
        SELECT claims.*, documents.filename AS document_name
        FROM claims
        JOIN documents
            ON claims.document_id = documents.id
        WHERE documents.session_id = ?
    """

    params = [
        session_id
    ]

    if document_id:

        query += """
            AND claims.document_id = ?
        """

        params.append(
            document_id
        )

    if verified_only:

        query += """
            AND claims.verified = 1
        """

    query += """
        ORDER BY claims.created_at DESC
    """

    with get_conn() as conn:

        rows = conn.execute(
            query,
            params,
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# RELATIONSHIPS
# ============================================================

@app.get(
    "/sessions/{session_id}/relationships"
)
def list_relationships(
    session_id: str,
    relationship_type: str | None = None,
):
    """
    List relationships where both claims belong to this session.
    """

    query = """
        SELECT
            relationships.*,
            source_claim.source_text AS source_text,
            source_claim.source_page AS source_page,
            source_claim.document_id AS source_document_id,
            source_claim.verified AS source_verified,
            source_document.filename AS source_document_name,
            target_claim.source_text AS target_text,
            target_claim.source_page AS target_page,
            target_claim.document_id AS target_document_id,
            target_claim.verified AS target_verified,
            target_document.filename AS target_document_name
        FROM relationships

        JOIN claims AS source_claim
            ON relationships.source_claim_id =
               source_claim.id

        JOIN documents AS source_document
            ON source_claim.document_id =
               source_document.id

        JOIN claims AS target_claim
            ON relationships.target_claim_id =
               target_claim.id

        JOIN documents AS target_document
            ON target_claim.document_id =
               target_document.id

        WHERE source_document.session_id = ?
          AND target_document.session_id = ?
    """

    params = [
        session_id,
        session_id,
    ]

    if relationship_type:

        query += """
            AND relationships.relationship_type = ?
        """

        params.append(
            relationship_type
        )

    query += """
        ORDER BY relationships.created_at DESC
    """

    with get_conn() as conn:

        rows = conn.execute(
            query,
            params,
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["claim_a"] = {
            "id": item["source_claim_id"],
            "document_id": item["source_document_id"],
            "source_text": item["source_text"],
            "source_page": item["source_page"],
            "verified": bool(item["source_verified"]),
            "document_name": item["source_document_name"],
        }
        item["claim_b"] = {
            "id": item["target_claim_id"],
            "document_id": item["target_document_id"],
            "source_text": item["target_text"],
            "source_page": item["target_page"],
            "verified": bool(item["target_verified"]),
            "document_name": item["target_document_name"],
        }
        result.append(item)

    return result


# ============================================================
# RELATIONSHIP DETAIL
# ============================================================

@app.get(
    "/sessions/{session_id}/relationships/{relationship_id}"
)
def relationship_detail(
    session_id: str,
    relationship_id: str,
):
    """
    Fact Court view.

    Returns both claims, their evidence, and their documents.
    """

    with get_conn() as conn:

        rel = conn.execute(
            """
            SELECT relationships.*
            FROM relationships

            JOIN claims AS source_claim
                ON relationships.source_claim_id =
                   source_claim.id

            JOIN documents AS source_document
                ON source_claim.document_id =
                   source_document.id

            JOIN claims AS target_claim
                ON relationships.target_claim_id =
                   target_claim.id

            JOIN documents AS target_document
                ON target_claim.document_id =
                   target_document.id

            WHERE relationships.id = ?
              AND source_document.session_id = ?
              AND target_document.session_id = ?
            """,
            (
                relationship_id,
                session_id,
                session_id,
            ),
        ).fetchone()

        if not rel:
            raise HTTPException(
                status_code=404,
                detail="relationship not found",
            )

        rel = dict(rel)

        claim_a = dict(
            conn.execute(
                """
                SELECT *
                FROM claims
                WHERE id = ?
                """,
                (
                    rel["source_claim_id"],
                ),
            ).fetchone()
        )

        claim_b = dict(
            conn.execute(
                """
                SELECT *
                FROM claims
                WHERE id = ?
                """,
                (
                    rel["target_claim_id"],
                ),
            ).fetchone()
        )

        doc_a = dict(
            conn.execute(
                """
                SELECT *
                FROM documents
                WHERE id = ?
                """,
                (
                    claim_a["document_id"],
                ),
            ).fetchone()
        )

        doc_b = dict(
            conn.execute(
                """
                SELECT *
                FROM documents
                WHERE id = ?
                """,
                (
                    claim_b["document_id"],
                ),
            ).fetchone()
        )

    return {
        "relationship": rel,
        "claim_a": claim_a,
        "claim_b": claim_b,
        "document_a": doc_a,
        "document_b": doc_b,
    }


# ============================================================
# SESSION STATS
# ============================================================

@app.get(
    "/sessions/{session_id}/stats"
)
def stats(
    session_id: str,
):
    """
    Statistics for one session only.
    """

    with get_conn() as conn:

        n_docs = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM documents
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()["c"]

        n_claims = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM claims
            JOIN documents
                ON claims.document_id = documents.id
            WHERE documents.session_id = ?
              AND claims.verified = 1
            """,
            (session_id,),
        ).fetchone()["c"]

        n_unverified = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM claims
            JOIN documents
                ON claims.document_id = documents.id
            WHERE documents.session_id = ?
              AND claims.verified = 0
            """,
            (session_id,),
        ).fetchone()["c"]

        n_rel = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM relationships
            JOIN claims AS source_claim
                ON relationships.source_claim_id =
                   source_claim.id
            JOIN documents AS source_document
                ON source_claim.document_id =
                   source_document.id
            JOIN claims AS target_claim
                ON relationships.target_claim_id =
                   target_claim.id
            JOIN documents AS target_document
                ON target_claim.document_id =
                   target_document.id
            WHERE source_document.session_id = ?
              AND target_document.session_id = ?
            """,
            (
                session_id,
                session_id,
            ),
        ).fetchone()["c"]

        by_type = conn.execute(
            """
            SELECT
                relationships.relationship_type,
                COUNT(*) AS c

            FROM relationships

            JOIN claims AS source_claim
                ON relationships.source_claim_id =
                   source_claim.id

            JOIN documents AS source_document
                ON source_claim.document_id =
                   source_document.id

            JOIN claims AS target_claim
                ON relationships.target_claim_id =
                   target_claim.id

            JOIN documents AS target_document
                ON target_claim.document_id =
                   target_document.id

            WHERE source_document.session_id = ?
              AND target_document.session_id = ?

            GROUP BY relationships.relationship_type
            """,
            (
                session_id,
                session_id,
            ),
        ).fetchall()

    return {
        "session_id": session_id,
        "documents": n_docs,
        "verified_claims": n_claims,
        "unverified_claims": n_unverified,
        "relationships": n_rel,
        "relationships_by_type": {
            row["relationship_type"]: row["c"]
            for row in by_type
        },
    }

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """
    Delete a session and all of its associated data.

    Removes:
    - relationships
    - claims
    - evidence blocks
    - documents
    - uploaded PDF files
    - session record
    """

    # --------------------------------------------------------
    # Find session and its documents
    # --------------------------------------------------------

    with get_conn() as conn:
        session = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if not session:
            raise HTTPException(
                status_code=404,
                detail="session not found",
            )

        documents = conn.execute(
            """
            SELECT id
            FROM documents
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchall()

        document_ids = [
            row["id"]
            for row in documents
        ]

        # ----------------------------------------------------
        # Delete relationships
        # ----------------------------------------------------

        if document_ids:
            placeholders = ",".join(
                "?" for _ in document_ids
            )

            conn.execute(
                f"""
                DELETE FROM relationships
                WHERE source_claim_id IN (
                    SELECT id
                    FROM claims
                    WHERE document_id IN ({placeholders})
                )
                OR target_claim_id IN (
                    SELECT id
                    FROM claims
                    WHERE document_id IN ({placeholders})
                )
                """,
                tuple(document_ids) + tuple(document_ids),
            )

            # ------------------------------------------------
            # Delete claims
            # ------------------------------------------------

            conn.execute(
                f"""
                DELETE FROM claims
                WHERE document_id IN ({placeholders})
                """,
                tuple(document_ids),
            )

            # ------------------------------------------------
            # Delete evidence blocks
            # ------------------------------------------------

            conn.execute(
                f"""
                DELETE FROM evidence_blocks
                WHERE document_id IN ({placeholders})
                """,
                tuple(document_ids),
            )

            # ------------------------------------------------
            # Delete documents
            # ------------------------------------------------

            conn.execute(
                """
                DELETE FROM documents
                WHERE session_id = ?
                """,
                (session_id,),
            )

        # ----------------------------------------------------
        # Delete session
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )

        conn.commit()

    # --------------------------------------------------------
    # Delete uploaded PDF files
    # --------------------------------------------------------

    deleted_files = 0

    for document_id in document_ids:
        pdf_path = UPLOAD_DIR / f"{document_id}.pdf"

        if pdf_path.exists():
            pdf_path.unlink()
            deleted_files += 1

    return {
        "session_id": session_id,
        "status": "deleted",
        "documents_deleted": len(document_ids),
        "files_deleted": deleted_files,
    }


@app.delete("/sessions/{session_id}/documents/{document_id}")
def delete_document(
    session_id: str,
    document_id: str,
):
    """
    Delete one document and all data derived from it.
    """

    # --------------------------------------------------------
    # Find document and verify it belongs to this session
    # --------------------------------------------------------

    with get_conn() as conn:
        document = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE id = ?
              AND session_id = ?
            """,
            (
                document_id,
                session_id,
            ),
        ).fetchone()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="document not found in this session",
            )

        # ----------------------------------------------------
        # Delete relationships involving this document's claims
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM relationships
            WHERE source_claim_id IN (
                SELECT id
                FROM claims
                WHERE document_id = ?
            )
            OR target_claim_id IN (
                SELECT id
                FROM claims
                WHERE document_id = ?
            )
            """,
            (
                document_id,
                document_id,
            ),
        )

        # ----------------------------------------------------
        # Delete claims
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM claims
            WHERE document_id = ?
            """,
            (document_id,),
        )

        # ----------------------------------------------------
        # Delete evidence blocks
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM evidence_blocks
            WHERE document_id = ?
            """,
            (document_id,),
        )

        # ----------------------------------------------------
        # Delete document
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM documents
            WHERE id = ?
              AND session_id = ?
            """,
            (
                document_id,
                session_id,
            ),
        )

        conn.commit()

    # --------------------------------------------------------
    # Delete uploaded PDF
    # --------------------------------------------------------

    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"

    file_deleted = False

    if pdf_path.exists():
        pdf_path.unlink()
        file_deleted = True

    return {
        "session_id": session_id,
        "document_id": document_id,
        "status": "deleted",
        "file_deleted": file_deleted,
    }