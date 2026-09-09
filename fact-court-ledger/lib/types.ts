// Centralized types for the Fact Knowledge Layer API.
//
// The backend's response shapes aren't fully pinned down, so every interface
// here is intentionally permissive: known fields are typed, everything else
// falls through `[key: string]: unknown` so the UI never breaks on a field
// it doesn't recognize. Components should use the accessor helpers in
// `lib/utils.ts` rather than reaching into raw fields directly.

export interface Session {
  id: string;
  created_at?: string;
  name?: string;
  [key: string]: unknown;
}

export interface DocumentItem {
  id: string;
  filename?: string;
  status?: string;
  claim_count?: number;
  created_at?: string;
  page_count?: number;
  [key: string]: unknown;
}

export interface Evidence {
  text?: string;
  page?: number;
  document_id?: string;
  document_name?: string;
  [key: string]: unknown;
}

export interface Claim {
  id: string;
  text?: string;
  document_id?: string;
  document_name?: string;
  verified?: boolean;
  evidence?: Evidence[];
  evidence_count?: number;
  [key: string]: unknown;
}

// The three relationship types the assignment names explicitly. The backend
// may return others — those are treated as unknown-but-valid, not errors.
export type KnownRelationshipType = "corroborates" | "contradicts" | "reconciles";

export interface Relationship {
  id: string;
  type?: string;
  claim_a?: Claim;
  claim_b?: Claim;
  claim_a_id?: string;
  claim_b_id?: string;
  reasoning?: string;
  [key: string]: unknown;
}

export interface Stats {
  documents?: number;
  claims?: number;
  relationships?: number;
  [key: string]: unknown;
}

export interface ApiError {
  message: string;
  status?: number;
}
