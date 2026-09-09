import { BadgeCheck } from "lucide-react";
import type { Claim, DocumentItem } from "@/lib/types";
import {
  claimText,
  claimDocumentName,
  claimEvidenceCount,
} from "@/lib/utils";

export function ClaimCard({
  claim,
  documents = [],
  onClick,
}: {
  claim: Claim;
  documents?: DocumentItem[];
  onClick?: () => void;
}) {
  const evidenceCount = claimEvidenceCount(claim);

  return (
    <button
      onClick={onClick}
      className="w-full text-left border border-[var(--line)] rounded-lg p-4 bg-[var(--paper-raised)] hover:border-[var(--ink-faint)] transition-colors cursor-pointer"
    >
      <p className="text-sm text-[var(--ink)] leading-relaxed">
        {claimText(claim)}
      </p>

      <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-3 text-xs text-[var(--ink-faint)]">
        <span>{claimDocumentName(claim, documents)}</span>

        {evidenceCount > 0 && (
          <span>
            {evidenceCount} evidence{" "}
            {evidenceCount === 1 ? "block" : "blocks"}
          </span>
        )}

        {claim.verified && (
          <span className="flex items-center gap-1 text-[var(--accent)]">
            <BadgeCheck size={12} strokeWidth={2} />
            Verified
          </span>
        )}
      </div>
    </button>
  );
}