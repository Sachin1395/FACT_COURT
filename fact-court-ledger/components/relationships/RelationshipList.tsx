import { Link2, ArrowRight, Scale } from "lucide-react";
import type { Relationship } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";
import { claimDocumentName, claimText, relationshipClaimA, relationshipClaimB, relationshipType } from "@/lib/utils";
import { TypeBadge } from "./TypeBadge";

interface RelationshipListProps {
  relationships: Relationship[] | null;
  isFiltered: boolean;
  onSelect: (relationship: Relationship) => void;
}

export function RelationshipList({ relationships, isFiltered, onSelect }: RelationshipListProps) {
  if (relationships === null) return <LoadingSkeleton variant="row" count={6} />;

  if (relationships.length === 0) {
    return <EmptyState icon={<Link2 size={22} strokeWidth={1.25} />} title={isFiltered ? "No matching relationships." : "No relationships found"} description={isFiltered ? undefined : "Upload more documents or change your filters."} />;
  }

  return (
    <div className="ledger-shell">
      <div className="ledger-scroll thin-scroll">
        <table className="ledger-table relationship-ledger">
          <thead>
            <tr>
              <th className="w-28">ID</th>
              <th>Claim A</th>
              <th className="w-40">Relation</th>
              <th>Claim B</th>
              <th className="w-28">Review</th>
            </tr>
          </thead>
          <tbody>
            {relationships.map((rel) => {
              const a = relationshipClaimA(rel);
              const b = relationshipClaimB(rel);
              return (
                <tr key={rel.id} onClick={() => onSelect(rel)} className="ledger-row">
                  <td><span className="ledger-id">{rel.id.slice(0, 8)}</span></td>
                  <td>
                    <div className="ledger-claim line-clamp-2">{claimText(a)}</div>
                    <div className="ledger-source">{claimDocumentName(a) || "—"}</div>
                  </td>
                  <td>
                    <div className="flex flex-col items-start gap-1.5">
                      <TypeBadge type={relationshipType(rel)} />
                      <span className="text-[10px] text-[var(--ink-faint)] flex items-center gap-1"><Scale size={10} /> fact link</span>
                    </div>
                  </td>
                  <td>
                    <div className="ledger-claim line-clamp-2">{claimText(b)}</div>
                    <div className="ledger-source">{claimDocumentName(b) || "—"}</div>
                  </td>
                  <td><span className="ledger-open"><ArrowRight size={13} /> Open</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="ledger-footer">{relationships.length} {relationships.length === 1 ? "relationship" : "relationships"} · Select a row for Fact Court</div>
    </div>
  );
}
