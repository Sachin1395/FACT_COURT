import { FileText } from "lucide-react";
import type { Claim } from "@/lib/types";
import {
  claimText,
  claimDocumentName,
  claimEvidenceList,
  evidenceText,
  evidencePage,
  evidenceDocumentName,
} from "@/lib/utils";
import { Drawer } from "../ui/Drawer";

export function ClaimDetail({
  claim,
  onClose,
}: {
  claim: Claim | null;
  onClose: () => void;
}) {
  const evidence = claim ? claimEvidenceList(claim) : [];

  return (
    <Drawer open={!!claim} onClose={onClose} title="Claim">
      {claim && (
        <div className="flex flex-col gap-6">
          <div>
            <p className="text-base text-[var(--ink)] leading-relaxed font-serif">
              {claimText(claim)}
            </p>
            <div className="flex items-center gap-1.5 text-xs text-[var(--ink-faint)] mt-2.5">
              <FileText size={12} strokeWidth={1.75} />
              {claimDocumentName(claim)}
              {claim.verified && (
                <span className="text-[var(--accent)] ml-1">· Verified</span>
              )}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-medium tracking-wide text-[var(--ink-faint)] uppercase mb-2.5">
              Evidence
            </h3>
            {evidence.length === 0 ? (
              <p className="text-sm text-[var(--ink-faint)]">
                No evidence provided for this claim.
              </p>
            ) : (
              <div className="flex flex-col gap-2.5">
                {evidence.map((ev, i) => (
                  <div
                    key={i}
                    className="border-l-2 border-[var(--accent)] bg-[var(--accent-soft)]/50 rounded-r-md px-3.5 py-3"
                  >
                    <p className="text-sm text-[var(--ink)] italic leading-relaxed">
                      &ldquo;{evidenceText(ev)}&rdquo;
                    </p>
                    <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)] mt-2">
                      {evidenceDocumentName(ev) && <span>{evidenceDocumentName(ev)}</span>}
                      {evidencePage(ev) !== undefined && <span>Page {evidencePage(ev)}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
