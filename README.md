# ⚖️ Fact Court

### Don't compare documents. Compare the facts inside them — with evidence.

Fact Court is an **evidence-first intelligence layer** for discovering how claims across PDFs relate to each other.

Instead of asking an LLM:
> "Do these two documents agree?"

Fact Court turns every extracted statement into a **claim with evidence**, then puts potentially related claims through structured reasoning:

```text
PDF
  ↓
Evidence Blocks
  ↓
Extracted Claims (with quotes)
  ↓
Verified Claims (quotes checked)
  ↓
Candidate Matching
  ↓
FACT COURT
  ├── Deterministic rules (units, periods, scopes)
  └── LLM adjudication (semantic ambiguity)
  ↓
Verdict: CORROBORATES | CONTRADICTS | RECONCILES | UNCERTAIN
```

---

## The Problem

Documents don't agree neatly.

The same underlying fact might appear as:

| Document A | Document B | Status |
|---|---|---|
| Revenue: ₹1,000 crore | Net Sales: ₹10 billion | **CORROBORATES** (same after conversion) |
| GDP growth: 6.4% | GDP growth: 6.5% | **RECONCILES** (different estimate vintages) |
| FY23 revenue: ₹800 cr | FY24 revenue: ₹1,000 cr | **RECONCILES** (different reporting periods) |
| Revenue: ₹800 cr | Revenue: ₹1,000 cr | **CONTRADICTS?** (context-dependent) |

A naive system sees `800 ≠ 1000` and flags a contradiction.

**Fact Court investigates why the difference exists.**

---

## The Solution

**Evidence-first design:**

Every claim carries:
- The exact quote from the PDF
- The page and document it came from
- Contextual metadata (period, scope, definition, units, basis)

Before any relationship is decided, quotes are **verified** against source text.

Then relationships proceed through **two layers**:

### Layer 1: Deterministic Rules

- Same value after unit normalization? → **CORROBORATES**
- Different reporting periods? → **RECONCILES**
- Different scopes (consolidated vs. standalone)? → **RECONCILES**
- Different definitions or bases? → **DEFER**

This eliminates obvious cases without LLM cost.

### Layer 2: Semantic Adjudication

Only ambiguous pairs go to Gemini. Examples:

- Two companies report "revenue" but one might include subsidies.
- "Net profit" vs. "operating profit" — are they describing the same metric?
- Different estimate vintage from the same source.

The LLM is an **adjudicator of ambiguity**, not the reasoning engine.

---

## Why This Matters

A relationship without provenance is not useful.

Every verdict Fact Court returns includes:

```json
{
  "source_claim_id": "claim-1",
  "target_claim_id": "claim-2",
  "relationship_type": "RECONCILES",
  "reason_code": "DIFFERENT_PERIOD",
  "explanation": "FY23 vs. FY24; not contradictory.",
  "confidence": 0.92,
  "decided_by": "rules"
}
```

You can trace it back through:

```
Relationship
  → Claim A (evidence quote + page)
  → Claim B (evidence quote + page)
  → Original PDFs
```

---

## Core Features

### ✅ Grounded
Every claim is tied to its evidence quote and source document.

### ✅ Explainable
Relationships include type, reasoning, and confidence — not just a label.

### ✅ Conservative
Candidate matching filters noise before expensive reasoning.

### ✅ Hybrid
Deterministic rules + LLM = faster, cheaper, safer.

### ✅ Incremental
Add new PDFs without rebuilding the entire analysis.

### ✅ Inspectable
Keep enough intermediate data to debug failures.

---

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind |
| API | FastAPI |
| PDF Extraction | PyMuPDF + pdfplumber |
| LLM | Google Gemini |
| Database | SQLite |
| Validation | Pydantic |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Google Gemini API key

### Backend

```bash
cd Backendzip
python -m venv venv
```

**Windows:**
```powershell
venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

Then:
```bash
pip install -r requirements.txt
```

Create `.env`:
```env
GEMINI_API_KEY=your_api_key_here
```

Run:
```bash
uvicorn main:app --reload
```

API: `http://localhost:8000/docs`

### Frontend

```bash
cd fact-court-ledger
npm install
npm run dev
```

Open: `http://localhost:3000`

---

## The Four Cases

The demo shows what Fact Court is designed for:

### Case 1: Corroboration
Same fact, different wording.
```
Document A: Revenue = ₹1,000 crore
Document B: Net Sales = ₹10 billion
                ↓
          CORROBORATES (after unit conversion)
```

### Case 2: Genuine Contradiction
Same metric, same context, different values.
```
Document A: Revenue FY24 = ₹1,200 cr
Document B: Revenue FY24 = ₹1,400 cr
                ↓
          CONTRADICTS
```

### Case 3: Context-Dependent Difference
Different values, but legitimate reason.
```
Document A: FY23 revenue = ₹800 cr
Document B: FY24 revenue = ₹1,000 cr
                ↓
          RECONCILES (different periods)
```

### Case 4: Failure Case
Show where extraction or reasoning breaks down and how the system handles it.

---

## How It Works

### 1. Upload PDFs

Create a session, upload documents.

### 2. Extract Evidence

PyMuPDF + pdfplumber break PDFs into meaningful blocks (not individual sentences).

### 3. Generate Claims

Gemini extracts structured facts from evidence blocks in batches.

Each claim includes the exact evidence quote.

### 4. Verify Evidence

Quote verification: Is the claim's evidence actually in the source block?

Prevents hallucinations from entering the knowledge layer.

### 5. Candidate Matching

Compare claims across documents using:
- Subject/predicate similarity
- Metric synonyms (revenue = net sales)
- Compatible units (₹ = €)
- Cross-document requirement

### 6. Deterministic Reasoning

Apply rules:
- Normalize units
- Detect period differences
- Identify scope mismatches
- Check definition compatibility

### 7. LLM Adjudication (if needed)

Ambiguous pairs go to Gemini with full context:
- Both claims
- Both evidence quotes
- Metadata (period, scope, definition, basis)

### 8. Store Relationships

Save the verdict with reasoning for inspection.

---

## API Examples

### Create a session
```bash
curl -X POST http://localhost:8000/sessions
```

### Upload PDFs
```bash
curl -X POST http://localhost:8000/sessions/{session_id}/documents \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf"
```

### Get claims
```bash
curl http://localhost:8000/sessions/{session_id}/claims
```

### Get relationships
```bash
curl http://localhost:8000/sessions/{session_id}/relationships
```

Full docs: `http://localhost:8000/docs`

---

## Architecture

```
User
  ↓
Next.js UI
  ↓
FastAPI
  ├── Session Management
  ├── PDF Extraction Pipeline
  │   ├── PyMuPDF (text)
  │   ├── pdfplumber (tables)
  │   └── Evidence blocks
  ├── Claim Generation
  │   ├── Batch extraction (Gemini)
  │   └── Evidence verification
  ├── Relationship Reasoning
  │   ├── Candidate matching
  │   ├── Deterministic rules
  │   └── LLM adjudication
  └── SQLite
      ├── Documents
      ├── Evidence blocks
      ├── Claims
      └── Relationships
```

---

## Design Decisions

### Why SQLite?
Zero infrastructure. Transactional. Easy to inspect. Perfect for a prototype.

### Why not compare every claim with every other?
O(n²) pairs. Most irrelevant. Candidate matching filters noise.

### Why deterministic rules before the LLM?
LLM calls are slow, expensive, and probabilistic.
Unit conversion and period detection should be instant and deterministic.

### Why verify LLM evidence quotes?
LLMs hallucinate. Evidence verification creates a quality gate:

```
Generated claim
  ↓
Does quoted text exist?
  ├─ YES → verified claim
  └─ NO → reject / inspect failure
```

### Why batch LLM calls?
Fewer requests, predictable token usage, and better traceability.

---

## Limitations

- **PDF extraction depends on structure.** Complex layouts may fragment sentences.
- **Text-based verification** doesn't capture visual context. Production would use bounding boxes.
- **Conservative candidate matching** may miss loosely related claims.
- **LLM reasoning is probabilistic.** Edge cases will occasionally fail.
- **SQLite limits scale.** For large-scale deployment, move to PostgreSQL + object storage.
- **Schema is fixed.** Production would need dynamic attributes.

---

## Next Steps

- **Better entity resolution:** Normalize company names, subsidiaries, geographies.
- **Semantic retrieval:** Use embeddings for candidate discovery.
- **Temporal knowledge:** Make fact timelines first-class.
- **Human review queue:** Flag low-confidence or uncertain relationships.
- **Production infrastructure:** Move to Postgres, object storage, background workers.
- **OCR support:** Handle scanned PDFs.
- **Evaluation framework:** Benchmark extraction and relationship accuracy.

---

## Project Structure

```
FACT_COURT/
├── Backendzip/
│   ├── app/
│   │   ├── db/
│   │   ├── extraction/
│   │   ├── matching/
│   │   ├── normalization/
│   │   ├── reasoning/
│   │   └── pipeline.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env
├── fact-court-ledger/
│   ├── app/
│   ├── components/
│   └── package.json
└── README.md
```

---

## 🎥 Demo

**[VIDEO_LINK_HERE]**

Shows:
- PDF upload and session setup
- Evidence-backed claim extraction
- Corroboration across documents
- Genuine contradiction detection
- Context-based reconciliation
- Failure handling

---

## Security

- **Never commit `.env` or API keys.**
- Uploaded PDFs may contain sensitive data — consider encryption and retention policies.
- Per-user authorization recommended for production.

---

## The Philosophy

> **Extract → Ground → Compare → Explain**

Don't build a black-box relationship graph.

Build an **inspectable, traceable, evidence-backed knowledge layer** where every verdict can be questioned, verified, and improved.

---

## License

Superjoin VIT 2026 Engineering Intern Hiring Assignment.

---

**Built with curiosity, structured evidence, and a healthy distrust of unsupported facts.**
