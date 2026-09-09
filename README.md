# ⚖️ Fact Court

### Don't compare documents. Compare the facts inside them — with evidence.

Fact Court is an **evidence-first intelligence layer** for discovering how claims across PDFs relate to each other.

Instead of asking an LLM *"Do these documents agree?"*, Fact Court builds an auditable chain:

```text
PDF
 ↓
Evidence Blocks
 ↓
Claims + Evidence
 ↓
Evidence Verification
 ↓
Candidate Matching
 ↓
Fact Court
 ├── Deterministic checks
 └── LLM adjudication
 ↓
CORROBORATES | CONTRADICTS | RECONCILES | UNCERTAIN
```

The key idea: **a different number does not automatically mean a different fact.**

---

## Why Fact Court?

Documents express the same facts differently.

```text
₹1,266 million
       ≈
₹126.6 crore
       ↓
CORROBORATES
```

Or:

```text
GDP growth: 6.4%
GDP growth: 6.5%
       ↓
Different estimate vintage
       ↓
RECONCILES
```

Fact Court considers **period, scope, units, definitions, basis and methodology** before calling something a contradiction.

Every verdict can be traced back to the original evidence.

---

## How It Works

**1. Extract**  
PDFs are split into page-level evidence blocks using PyMuPDF.

**2. Generate claims**  
Gemini extracts structured claims with value, unit, period, scope, definition and an evidence quote.

**3. Verify**  
The evidence quote is checked against the extracted source text. Unverified claims are not used for relationship decisions.

**4. Match**  
Candidate claims are found using subject/predicate similarity and normalized values/units.

**5. Adjudicate**  
Obvious cases are handled deterministically. Ambiguous cases are sent to Gemini with both claims and their evidence.

---

## ⚖️ The Four Verdicts

| Verdict | Meaning |
|---|---|
| **CORROBORATES** | Same fact, compatible values/context |
| **CONTRADICTS** | Same fact, same context, materially conflicting |
| **RECONCILES** | Difference explained by period, scope, definition, vintage, etc. |
| **UNCERTAIN** | Evidence/context is insufficient |

Each relationship stores its **reason, confidence and source claims**.

---

## Incremental Processing

Documents belong to a session.

```text
PDF 1 → Claims A

PDF 2 → Claims B → compare with A

PDF 3 → Claims C → compare with A + B
```

New documents are added incrementally without rebuilding the entire session.

Large PDFs are processed in **token-aware batches** with rate limiting and retry handling.

---

## Design Decisions

### Evidence before reasoning

The LLM cannot be treated as the source of truth. Claims must point back to document evidence.

### Deterministic before LLM

Unit normalization, period differences and other obvious comparisons should not require an LLM call.

### Context before contradiction

`800 ≠ 1000` is not enough. The system checks whether the claims actually describe the same fact in the same context.

### Safe uncertainty

When evidence is insufficient, Fact Court returns `UNCERTAIN` instead of inventing an explanation.

---

## Demo

**Video:** [VIDEO_LINK_HERE]

The demo covers the four required cases:

1. **Corroboration** — same fact expressed differently
2. **Contradiction** — same fact and context with conflicting values
3. **Reconciliation** — apparent conflict explained by context
4. **Failure** — extraction/reasoning failure and how it is handled

---

## Tech Stack

- **Frontend:** Next.js, TypeScript, Tailwind
- **Backend:** Python, FastAPI
- **PDF:** PyMuPDF
- **LLM:** Google Gemini
- **Database:** SQLite
- **Validation:** Pydantic

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

**macOS/Linux:**

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

API docs:

`http://localhost:8000/docs`

### Frontend

```bash
cd fact-court-ledger
npm install
npm run dev
```

Open:

`http://localhost:3000`

---

## Limitations

- PDF extraction can struggle with complex layouts.
- Scanned PDFs require OCR.
- Ambiguous claims may require human review.
- Pairwise matching becomes expensive as the claim set grows.

## Next Steps

- OCR support
- Semantic retrieval for candidate matching
- Human review for uncertain relationships
- Better entity resolution
- Production storage/background workers

---

## The Principle

> **Extract → Ground → Compare → Explain**

Fact Court is intentionally small: an **inspectable evidence layer**, not a black-box document comparison system.

**Built with a healthy distrust of unsupported facts.**
