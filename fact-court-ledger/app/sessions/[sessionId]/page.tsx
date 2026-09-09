"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Upload as UploadIcon, Trash2, Loader2, ChevronLeft } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { Stats } from "@/components/dashboard/Stats";
import { DashboardTabs, type DashboardTab } from "@/components/dashboard/DashboardTabs";
import { DocumentUpload } from "@/components/documents/DocumentUpload";
import { DocumentList } from "@/components/documents/DocumentList";
import { RelationshipFilters } from "@/components/relationships/RelationshipFilters";
import { RelationshipList } from "@/components/relationships/RelationshipList";
import { FactCourt } from "@/components/relationships/FactCourt";
import { ClaimFilters } from "@/components/claims/ClaimFilters";
import { ClaimList } from "@/components/claims/ClaimList";
import { ClaimDetail } from "@/components/claims/ClaimDetail";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  listDocuments,
  uploadDocuments,
  deleteDocument,
  listClaims,
  listRelationships,
  getRelationship,
  getStats,
  deleteSession,
} from "@/lib/api";
import type { Claim, DocumentItem, Relationship, Stats as StatsType } from "@/lib/types";
import {
  claimText,
  claimDocumentName,
  claimEvidenceList,
  evidenceText,
  relationshipType,
  relationshipClaimA,
  relationshipClaimB,
  relationshipReasoning,
  debounce,
  shortId,
} from "@/lib/utils";

export default function SessionDashboardPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = decodeURIComponent(params.sessionId);
  const router = useRouter();

  const [tab, setTab] = useState<DashboardTab>("documents");

  const [documents, setDocuments] = useState<DocumentItem[] | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);

  const [claims, setClaims] = useState<Claim[] | null>(null);
  const [claimsError, setClaimsError] = useState<string | null>(null);
  const [claimDocFilter, setClaimDocFilter] = useState("");
  const [claimVerifiedOnly, setClaimVerifiedOnly] = useState(false);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);

  const [relationships, setRelationships] = useState<Relationship[] | null>(null);
  const [relationshipsError, setRelationshipsError] = useState<string | null>(null);
  const [relTypeFilter, setRelTypeFilter] = useState("all");
  const [factSearch, setFactSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [stats, setStats] = useState<StatsType | null>(null);

  const [selectedRelId, setSelectedRelId] = useState<string | null>(null);
  const [relDetail, setRelDetail] = useState<Relationship | null>(null);
  const [relDetailLoading, setRelDetailLoading] = useState(false);
  const [relDetailError, setRelDetailError] = useState<string | null>(null);

  const [deletingSession, setDeletingSession] = useState(false);
  const [confirmDeleteSession, setConfirmDeleteSession] = useState(false);

  const debouncedSetSearch = useMemo(() => debounce(setDebouncedSearch, 200), []);

  useEffect(() => {
    debouncedSetSearch(factSearch);
  }, [factSearch, debouncedSetSearch]);

  const loadDocuments = useCallback(async () => {
    setDocumentsError(null);
    try {
      setDocuments(await listDocuments(sessionId));
    } catch {
      setDocumentsError("Unable to load documents.");
    }
  }, [sessionId]);

  const loadClaims = useCallback(async () => {
    setClaimsError(null);
    try {
      setClaims(
        await listClaims(sessionId, {
          documentId: claimDocFilter || undefined,
          verifiedOnly: claimVerifiedOnly,
        })
      );
    } catch {
      setClaimsError("Unable to load claims.");
    }
  }, [sessionId, claimDocFilter, claimVerifiedOnly]);

  const loadRelationships = useCallback(async () => {
    setRelationshipsError(null);
    try {
      setRelationships(await listRelationships(sessionId));
    } catch {
      setRelationshipsError("Unable to load relationships.");
    }
  }, [sessionId]);

  const loadStats = useCallback(async () => {
    try {
      setStats(await getStats(sessionId));
    } catch {
      // stats are supplementary — fail quietly, row just stays in a loading state
    }
  }, [sessionId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadDocuments(), loadClaims(), loadRelationships(), loadStats()]);
  }, [loadDocuments, loadClaims, loadRelationships, loadStats]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll();

    const timer = window.setInterval(() => {
      refreshAll();
    }, 3000);

    return () => window.clearInterval(timer);
  }, [sessionId, refreshAll]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadClaims();
  }, [loadClaims]);

  async function handleUpload(files: File[]) {
    await uploadDocuments(sessionId, files);
    await refreshAll();
  }

  async function handleDeleteDocument(documentId: string) {
    await deleteDocument(sessionId, documentId);
    await refreshAll();
  }

  async function handleDeleteSession() {
    setDeletingSession(true);
    try {
      await deleteSession(sessionId);
      router.push("/");
    } catch {
      setDeletingSession(false);
      setConfirmDeleteSession(false);
    }
  }

  async function openRelationship(rel: Relationship) {
    setSelectedRelId(rel.id);
    setRelDetail(rel);
    setRelDetailLoading(true);
    setRelDetailError(null);
    try {
      const full = await getRelationship(sessionId, rel.id);
      setRelDetail(full);
    } catch {
      setRelDetailError("Unable to load this relationship's evidence.");
    } finally {
      setRelDetailLoading(false);
    }
  }

  const availableRelTypes = useMemo(() => {
    if (!relationships) return [];
    const set = new Set<string>();
    for (const r of relationships) set.add(relationshipType(r));
    return Array.from(set);
  }, [relationships]);

  const filteredRelationships = useMemo(() => {
    if (!relationships) return null;
    const q = debouncedSearch.trim().toLowerCase();
    return relationships.filter((rel) => {
      const type = relationshipType(rel);
      if (relTypeFilter !== "all" && type !== relTypeFilter) return false;
      if (!q) return true;
      const claimA = relationshipClaimA(rel);
      const claimB = relationshipClaimB(rel);
      const haystack = [
        claimText(claimA),
        claimText(claimB),
        claimDocumentName(claimA),
        claimDocumentName(claimB),
        relationshipReasoning(rel),
        ...claimEvidenceList(claimA).map(evidenceText),
        ...claimEvidenceList(claimB).map(evidenceText),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [relationships, relTypeFilter, debouncedSearch]);

  const filteredClaims = useMemo(() => {
    if (!claims) return null;
    const q = debouncedSearch.trim().toLowerCase();
    if (!q) return claims;
    return claims.filter((claim) => {
      const haystack = [
        claimText(claim),
        claimDocumentName(claim),
        ...claimEvidenceList(claim).map(evidenceText),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [claims, debouncedSearch]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        right={
          <Button variant="ghost" size="sm" onClick={() => router.push("/")}>
            <ChevronLeft size={14} strokeWidth={2} />
            Sessions
          </Button>
        }
      />

      <main className="flex-1 max-w-5xl w-full mx-auto px-5 sm:px-8 py-8 flex flex-col gap-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs text-[var(--ink-faint)] mb-1">Session</p>
            <h1 className="font-mono text-sm text-[var(--ink)]">{shortId(sessionId, 16)}</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                document.getElementById("upload-section")?.scrollIntoView({ behavior: "smooth" })
              }
            >
              <UploadIcon size={14} strokeWidth={1.75} />
              Upload PDFs
            </Button>
            <Button size="sm" variant="danger" onClick={() => setConfirmDeleteSession(true)}>
              <Trash2 size={14} strokeWidth={1.75} />
              Delete Session
            </Button>
          </div>
        </div>

        <Stats stats={stats} loading={stats === null} />

        <section id="upload-section" className="workspace-strip">
          <div>
            <p className="text-[10px] uppercase tracking-[.12em] font-semibold text-[var(--ink-faint)]">Evidence workspace</p>
            <p className="text-sm text-[var(--ink-soft)] mt-1">Upload source PDFs, then review the extracted claims and cross-document links below.</p>
          </div>
          <DocumentUpload onUpload={handleUpload} />
        </section>

        <section className="flex flex-col gap-4">
          <DashboardTabs active={tab} onChange={setTab} />

          {tab === "relationships" && (
            <div className="flex flex-col gap-4">
              <RelationshipFilters
                search={factSearch}
                onSearchChange={setFactSearch}
                activeType={relTypeFilter}
                onTypeChange={setRelTypeFilter}
                availableTypes={availableRelTypes}
              />
              {relationshipsError ? (
                <ErrorState message={relationshipsError} onRetry={loadRelationships} />
              ) : (
                <RelationshipList
                  relationships={filteredRelationships}
                  isFiltered={!!debouncedSearch || relTypeFilter !== "all"}
                  onSelect={openRelationship}
                />
              )}
            </div>
          )}

          {tab === "claims" && (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="relative flex-1 max-w-xs">
                  <input
                    value={factSearch}
                    onChange={(e) => setFactSearch(e.target.value)}
                    placeholder="Search facts…"
                    className="w-full text-sm border border-[var(--line-strong)] rounded-md bg-[var(--paper-raised)] px-3 py-1.5 text-[var(--ink)] placeholder:text-[var(--ink-faint)]"
                  />
                </div>
                <ClaimFilters
                  documents={documents ?? []}
                  documentId={claimDocFilter}
                  onDocumentChange={setClaimDocFilter}
                  verifiedOnly={claimVerifiedOnly}
                  onVerifiedChange={setClaimVerifiedOnly}
                />
              </div>
              {claimsError ? (
                <ErrorState message={claimsError} onRetry={loadClaims} />
              ) : (
                <ClaimList
                  claims={filteredClaims}
                  documents={documents ?? []}
                  isFiltered={!!debouncedSearch}
                  onSelect={setSelectedClaim}
                />
              )}
            </div>
          )}

          {tab === "documents" && (
            <DocumentList documents={documents} onDelete={handleDeleteDocument} />
          )}
        </section>
      </main>

      <FactCourt
        open={!!selectedRelId}
        onClose={() => setSelectedRelId(null)}
        relationship={relDetail}
        loading={relDetailLoading}
        error={relDetailError}
        onRetry={() => {
          const rel = relationships?.find((r) => r.id === selectedRelId);
          if (rel) openRelationship(rel);
        }}
      />

      <ClaimDetail claim={selectedClaim} onClose={() => setSelectedClaim(null)} />

      <Modal
        open={confirmDeleteSession}
        onClose={() => setConfirmDeleteSession(false)}
        title="Delete session?"
        footer={
          <>
            <Button size="sm" variant="secondary" onClick={() => setConfirmDeleteSession(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={handleDeleteSession}
              disabled={deletingSession}
            >
              {deletingSession && <Loader2 size={13} className="animate-spin" strokeWidth={2} />}
              Delete Session
            </Button>
          </>
        }
      >
        This permanently removes documents, claims, evidence, relationships, and uploaded PDFs.
      </Modal>
    </div>
  );
}
