import type { Claim, Relationship } from "@/lib/types";
import {
  relationshipType,
  relationshipClaimA,
  relationshipClaimB,
  relationshipReasoning,
  claimText,
  claimDocumentName,
  claimEvidenceList,
  evidenceText,
  evidencePage,
  evidenceDocumentName,
} from "@/lib/utils";
import { Drawer } from "../ui/Drawer";
import { TypeBadge } from "./TypeBadge";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";
import { ErrorState } from "../ui/ErrorState";

function ClaimColumn({ label, claim }: { label: string; claim?: Claim }) {
  const evidence = claimEvidenceList(claim);

  return (
    <div className="flex-1 min-w-0">
      <h3 className="text-xs font-medium tracking-wide text-[var(--ink-faint)] uppercase mb-2">
        {label}
      </h3>
      <p className="text-sm text-[var(--ink)] leading-relaxed font-serif">
        {claimText(claim)}
      </p>
      <p className="text-xs text-[var(--ink-faint)] mt-2">{claimDocumentName(claim)}</p>

      <div className="mt-4">
        <h4 className="text-[11px] font-medium tracking-wide text-[var(--ink-faint)] uppercase mb-2">
          Evidence
        </h4>
        {evidence.length === 0 ? (
          <p className="text-xs text-[var(--ink-faint)]">No evidence available.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {evidence.map((ev, i) => (
              <div
                key={i}
                className="border-l-2 border-[var(--accent)] bg-[var(--accent-soft)]/50 rounded-r-md px-3 py-2.5"
              >
                <p className="text-[13px] text-[var(--ink)] italic leading-relaxed">
                  &ldquo;{evidenceText(ev)}&rdquo;
                </p>
                <div className="flex items-center gap-2 text-[11px] text-[var(--ink-faint)] mt-1.5">
                  {evidenceDocumentName(ev) && <span>{evidenceDocumentName(ev)}</span>}
                  {evidencePage(ev) !== undefined && <span>Page {evidencePage(ev)}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface FactCourtProps {
  open: boolean;
  onClose: () => void;
  relationship: Relationship | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function FactCourt({ open, onClose, relationship, loading, error, onRetry }: FactCourtProps) {
  const claimA = relationship ? relationshipClaimA(relationship) : undefined;
  const claimB = relationship ? relationshipClaimB(relationship) : undefined;
  const reasoning = relationship ? relationshipReasoning(relationship) : undefined;

  return (
    <Drawer open={open} onClose={onClose} title="Fact Court">
      {loading && <LoadingSkeleton variant="card" count={2} />}

      {!loading && error && <ErrorState message={error} onRetry={onRetry} />}

      {!loading && !error && relationship && (
        <div className="flex flex-col gap-6">
          <div>
            <h3 className="text-xs font-medium tracking-wide text-[var(--ink-faint)] uppercase mb-2">
              Relationship
            </h3>
            <TypeBadge type={relationshipType(relationship)} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <ClaimColumn label="Claim A" claim={claimA} />
            <ClaimColumn label="Claim B" claim={claimB} />
          </div>

          <div className="border-t border-[var(--line)] pt-5">
            <h3 className="text-xs font-medium tracking-wide text-[var(--ink-faint)] uppercase mb-2">
              Why these facts are related
            </h3>
            <p className="text-sm text-[var(--ink-soft)] leading-relaxed">
              {reasoning || "No reasoning was provided by the backend for this relationship."}
            </p>
          </div>
        </div>
      )}
    </Drawer>
  );
}
