import type { Claim, DocumentItem, Evidence, Relationship } from "./types";

// Backend field names aren't fully pinned down (e.g. a claim's text might
// arrive as `text`, `claim_text`, or `content`). These helpers try the
// likely variants in order so the UI never shows "undefined".
function firstDefined<T = unknown>(
  obj: Record<string, unknown> | undefined,
  keys: string[]
): T | undefined {
  if (!obj) return undefined;
  for (const key of keys) {
    const value = obj[key];
    if (value !== undefined && value !== null && value !== "") {
      return value as T;
    }
  }
  return undefined;
}

export function shortId(id: string | undefined, length = 8): string {
  if (!id) return "—";
  return id.length > length ? id.slice(0, length) : id;
}

export function claimText(claim: Claim | undefined): string {
  return (
    firstDefined<string>(claim, ["text", "source_text", "claim_text", "content", "statement"]) ??
    "Untitled claim"
  );
}

export function claimDocumentName(
  claim: Claim | undefined,
  documents: DocumentItem[] = []
): string {
  if (!claim) return "Unknown document";

  // Backend already provides the filename
  if (claim.document_name) {
    return claim.document_name;
  }

  // Fallback: resolve filename from document_id
  if (claim.document_id) {
    const document = documents.find(
      (doc) => doc.id === claim.document_id
    );

    if (document?.filename) {
      return document.filename;
    }
  }

  return "Unknown document";
}

export function claimEvidenceList(claim: Claim | undefined): Evidence[] {
  if (!claim) return [];
  const list = firstDefined<Evidence[]>(claim, ["evidence", "evidence_blocks", "sources"]);
  return Array.isArray(list) ? list : [];
}

export function claimEvidenceCount(claim: Claim | undefined): number {
  const list = claimEvidenceList(claim);
  if (list.length) return list.length;
  return (
    firstDefined<number>(claim, ["evidence_count", "num_evidence"]) ?? 0
  );
}

export function evidenceText(evidence: Evidence | undefined): string {
  return (
    firstDefined<string>(evidence, ["text", "source_text", "quote", "excerpt", "snippet"]) ??
    ""
  );
}

export function evidencePage(evidence: Evidence | undefined): number | undefined {
  return firstDefined<number>(evidence, ["page", "source_page", "page_number"]);
}

export function evidenceDocumentName(evidence: Evidence | undefined): string | undefined {
  return firstDefined<string>(evidence, [
    "document_name",
    "document_filename",
    "source_document",
    "filename",
    "document_name",
  ]);
}

export function documentFilename(doc: DocumentItem | undefined): string {
  return (
    firstDefined<string>(doc, ["filename", "name", "file_name"]) ??
    "Untitled document"
  );
}

export function documentClaimCount(doc: DocumentItem | undefined): number | undefined {
  return firstDefined<number>(doc, ["claim_count", "claims_count", "num_claims"]);
}

export function documentStatus(doc: DocumentItem | undefined): string | undefined {
  return firstDefined<string>(doc, ["status", "processing_status"]);
}

export function relationshipType(rel: Relationship | undefined): string {
  return (
    firstDefined<string>(rel, ["type", "relationship_type", "relation"]) ??
    "unknown"
  ).toLowerCase();
}

export function relationshipReasoning(rel: Relationship | undefined): string | undefined {
  return firstDefined<string>(rel, [
    "reasoning",
    "explanation",
    "rationale",
    "why",
  ]);
}

export function relationshipClaimA(rel: Relationship | undefined): Claim | undefined {
  return firstDefined<Claim>(rel, ["claim_a", "claimA", "claim_1", "source_claim"]);
}

export function relationshipClaimB(rel: Relationship | undefined): Claim | undefined {
  return firstDefined<Claim>(rel, ["claim_b", "claimB", "claim_2", "target_claim"]);
}

export function statValue(
  stats: Record<string, unknown> | undefined,
  keys: string[]
): number {
  const value = firstDefined<number>(stats, keys);
  return typeof value === "number" ? value : 0;
}

export function formatDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  delayMs: number
): (...args: Args) => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (...args: Args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}
