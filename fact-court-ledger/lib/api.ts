import type { Session, DocumentItem, Claim, Evidence, Relationship, Stats, ApiError } from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiRequestError extends Error implements ApiError {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError("Couldn't reach the backend. Check that the API is running at " + BASE_URL + ".");
  }

  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string"
        ? body.detail
        : Array.isArray(body?.detail)
          ? body.detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join(", ")
          : "";
    } catch {}
    throw new ApiRequestError(detail || res.statusText || "Request failed", res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function listFrom<T>(payload: unknown, key: string): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    const value = (payload as Record<string, unknown>)[key];
    if (Array.isArray(value)) return value as T[];
  }
  return [];
}

function normalizeSession(raw: Record<string, unknown>): Session {
  return {
    ...raw,
    id: String(raw.id ?? raw.session_id),
    created_at: raw.created_at as string | undefined,
  };
}

function normalizeDocument(raw: Record<string, unknown>): DocumentItem {
  return {
    ...raw,
    id: String(raw.id ?? raw.document_id),
    filename: (raw.filename ?? raw.file_name ?? raw.name) as string | undefined,
    created_at: (raw.created_at ?? raw.uploaded_at) as string | undefined,
    status: raw.status as string | undefined,
  };
}

function normalizeClaim(raw: Record<string, unknown>, documentName?: string): Claim {
  const sourceText = (raw.source_text ?? raw.text ?? raw.claim_text ?? raw.content ?? raw.statement ?? "") as string;
  const evidence: Evidence[] = sourceText
    ? [{ text: sourceText, page: Number(raw.source_page ?? raw.page) || undefined, document_id: String(raw.document_id ?? ""), document_name: documentName ?? raw.document_name as string | undefined }]
    : [];

  return {
    ...raw,
    id: String(raw.id),
    text: sourceText || undefined,
    document_id: raw.document_id as string | undefined,
    document_name: documentName ?? raw.document_name as string | undefined,
    evidence,
    evidence_count: evidence.length,
    verified: Boolean(raw.verified),
  };
}

function normalizeRelationship(raw: Record<string, unknown>, claims?: Map<string, Claim>): Relationship {
  const relationship = (raw.relationship && typeof raw.relationship === "object")
    ? raw.relationship as Record<string, unknown>
    : raw;

  const claimA = raw.claim_a && typeof raw.claim_a === "object"
    ? normalizeClaim(raw.claim_a as Record<string, unknown>, raw.document_a && typeof raw.document_a === "object" ? String((raw.document_a as Record<string, unknown>).filename ?? "") : undefined)
    : claims?.get(String(relationship.source_claim_id));
  const claimB = raw.claim_b && typeof raw.claim_b === "object"
    ? normalizeClaim(raw.claim_b as Record<string, unknown>, raw.document_b && typeof raw.document_b === "object" ? String((raw.document_b as Record<string, unknown>).filename ?? "") : undefined)
    : claims?.get(String(relationship.target_claim_id));

  return {
    ...relationship,
    id: String(relationship.id),
    type: String(relationship.relationship_type ?? relationship.type ?? "unknown").toLowerCase(),
    claim_a_id: String(relationship.source_claim_id ?? ""),
    claim_b_id: String(relationship.target_claim_id ?? ""),
    claim_a: claimA,
    claim_b: claimB,
    reasoning: String(relationship.explanation ?? relationship.reasoning ?? relationship.rationale ?? ""),
  };
}

export async function listSessions(): Promise<Session[]> {
  const data = await request<unknown>("/sessions");
  return listFrom<Record<string, unknown>>(data, "sessions").map(normalizeSession);
}

export async function createSession(): Promise<Session> {
  return normalizeSession(await request<Record<string, unknown>>("/sessions", { method: "POST" }));
}

export async function getSession(sessionId: string): Promise<Session> {
  return normalizeSession(await request<Record<string, unknown>>(`/sessions/${encodeURIComponent(sessionId)}`));
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export async function uploadDocuments(sessionId: string, files: File[]): Promise<DocumentItem[]> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const data = await request<unknown>(`/sessions/${encodeURIComponent(sessionId)}/documents`, { method: "POST", body: form });
  return listFrom<Record<string, unknown>>(data, "documents").map(normalizeDocument);
}

export async function listDocuments(sessionId: string): Promise<DocumentItem[]> {
  const data = await request<unknown>(`/sessions/${encodeURIComponent(sessionId)}/documents`);
  return listFrom<Record<string, unknown>>(data, "documents").map(normalizeDocument);
}

export async function deleteDocument(sessionId: string, documentId: string): Promise<void> {
  await request(`/sessions/${encodeURIComponent(sessionId)}/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" });
}

export async function listClaims(sessionId: string, params?: { documentId?: string; verifiedOnly?: boolean }): Promise<Claim[]> {
  const search = new URLSearchParams();
  if (params?.documentId) search.set("document_id", params.documentId);
  if (params?.verifiedOnly) search.set("verified_only", "true");
  const qs = search.toString();
  const data = await request<unknown>(`/sessions/${encodeURIComponent(sessionId)}/claims${qs ? `?${qs}` : ""}`);
  return listFrom<Record<string, unknown>>(data, "claims").map((raw) => normalizeClaim(raw, raw.document_name as string | undefined));
}

export async function listRelationships(sessionId: string, relationshipType?: string): Promise<Relationship[]> {
  const search = new URLSearchParams();
  if (relationshipType && relationshipType !== "all") search.set("relationship_type", relationshipType);
  const qs = search.toString();
  const data = await request<unknown>(`/sessions/${encodeURIComponent(sessionId)}/relationships${qs ? `?${qs}` : ""}`);
  return listFrom<Record<string, unknown>>(data, "relationships").map((raw) => normalizeRelationship(raw));
}

export async function getRelationship(sessionId: string, relationshipId: string): Promise<Relationship> {
  const data = await request<Record<string, unknown>>(`/sessions/${encodeURIComponent(sessionId)}/relationships/${encodeURIComponent(relationshipId)}`);
  return normalizeRelationship(data);
}

export async function getStats(sessionId: string): Promise<Stats> {
  const raw = await request<Record<string, unknown>>(`/sessions/${encodeURIComponent(sessionId)}/stats`);
  return {
    ...raw,
    documents: Number(raw.documents ?? 0),
    claims: Number(raw.verified_claims ?? raw.claims ?? 0),
    relationships: Number(raw.relationships ?? 0),
  };
}
