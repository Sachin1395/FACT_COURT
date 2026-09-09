import type { DocumentItem } from "@/lib/types";
import { documentFilename } from "@/lib/utils";

interface ClaimFiltersProps {
  documents: DocumentItem[];
  documentId: string;
  onDocumentChange: (id: string) => void;
  verifiedOnly: boolean;
  onVerifiedChange: (v: boolean) => void;
}

export function ClaimFilters({
  documents,
  documentId,
  onDocumentChange,
  verifiedOnly,
  onVerifiedChange,
}: ClaimFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
        Document
        <select
          value={documentId}
          onChange={(e) => onDocumentChange(e.target.value)}
          className="border border-[var(--line-strong)] rounded-md bg-[var(--paper-raised)] text-[var(--ink)] text-sm px-2.5 py-1.5 cursor-pointer"
        >
          <option value="">All Documents</option>
          {documents.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {documentFilename(doc)}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)] cursor-pointer">
        Verified
        <select
          value={verifiedOnly ? "verified" : "all"}
          onChange={(e) => onVerifiedChange(e.target.value === "verified")}
          className="border border-[var(--line-strong)] rounded-md bg-[var(--paper-raised)] text-[var(--ink)] text-sm px-2.5 py-1.5 cursor-pointer"
        >
          <option value="all">All</option>
          <option value="verified">Verified</option>
        </select>
      </label>
    </div>
  );
}
