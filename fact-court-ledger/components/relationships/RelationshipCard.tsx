import { ChevronRight } from "lucide-react";
import type { Relationship } from "@/lib/types";
import {
  relationshipType,
  relationshipClaimA,
  relationshipClaimB,
  claimText,
  claimDocumentName,
} from "@/lib/utils";
import { TypeBadge } from "./TypeBadge";

export function RelationshipCard({
  relationship,
  onClick,
}: {
  relationship: Relationship;
  onClick: () => void;
}) {
  const claimA = relationshipClaimA(relationship);
  const claimB = relationshipClaimB(relationship);

  return (
    <button
      onClick={onClick}
      className="w-full text-left border border-[var(--line)] rounded-lg p-4 bg-[var(--paper-raised)] hover:border-[var(--ink-faint)] transition-colors cursor-pointer group"
    >
      <div className="flex items-center justify-between mb-3">
        <TypeBadge type={relationshipType(relationship)} />
        <ChevronRight
          size={15}
          strokeWidth={1.75}
          className="text-[var(--ink-faint)] group-hover:text-[var(--ink)] transition-colors"
        />
      </div>

      <p className="text-sm text-[var(--ink)] leading-relaxed">{claimText(claimA)}</p>

      <div className="flex items-center gap-2 my-2.5 text-[11px] text-[var(--ink-faint)]">
        <span className="truncate max-w-[45%]">{claimDocumentName(claimA)}</span>
        <span className="flex-1 h-px bg-[var(--line)]" />
        <span className="truncate max-w-[45%] text-right">{claimDocumentName(claimB)}</span>
      </div>

      <p className="text-sm text-[var(--ink-soft)] leading-relaxed">{claimText(claimB)}</p>
    </button>
  );
}
