# FACT COURT

### Evidence-First Fact Intelligence for Documents

**Superjoin · VIT 2026 · Engineering Intern Hiring Assignment**

> **FACT COURT turns scattered document statements into an evidence-grounded knowledge layer, then determines whether claims corroborate, contradict, or reconcile through context.**

---

## 🎥 Video Demo

### Demo Video — ≤ 3 Minutes

**[▶️ Watch the FACT COURT Demo](PASTE_YOUR_VIDEO_LINK_HERE)**

> Replace `PASTE_YOUR_VIDEO_LINK_HERE` with the final Loom / YouTube / Google Drive link before submission.

The demo covers the four cases requested in the assignment:

1. **CORROBORATES** — the same fact appears across documents using different wording or units.
2. **CONTRADICTS** — the same underlying metric materially disagrees under the same context.
3. **RECONCILES** — apparently different values are explained by context such as period, scope, units, definition, estimate vintage, or methodology.
4. **FAILURE / UNCERTAINTY** — an extraction or reasoning failure is surfaced instead of silently being treated as truth.

For the first three cases, the UI shows the supporting source evidence and the system's reasoning.

---

# 1. The Problem

Important facts are often scattered across documents.

The same underlying fact may be:

- expressed using different wording;
- represented using different units;
- reported for different time periods;
- reported at different scopes;
- defined differently;
- revised in later estimates;
- affected by methodology changes;
- or genuinely contradicted by another source.

A naive text-matching system can easily mistake contextual differences for contradictions.

For example:

```text
FY2024 Revenue = ₹8,142 crore

Q4 FY2024 Revenue = ₹2,076 crore
