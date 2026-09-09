import { ScrollText, Check, Minus } from "lucide-react";
import type { Claim, DocumentItem } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";
import { claimDocumentName, claimText, claimEvidenceList, evidencePage } from "@/lib/utils";

interface ClaimListProps {
  claims: Claim[] | null;
  documents: DocumentItem[];
  isFiltered: boolean;
  onSelect: (claim: Claim) => void;
}

export function ClaimList({
  claims,
  documents,
  isFiltered,
  onSelect,
}: ClaimListProps) {
  if (claims === null) return <LoadingSkeleton variant="row" count={6} />;

  if (claims.length === 0) {
    return <EmptyState icon={<ScrollText size={22} strokeWidth={1.25} />} title={isFiltered ? "No matching facts." : "No claims found."} />;
  }

  return (
    <div className="ledger-shell">
      <div className="ledger-scroll thin-scroll">
        <table className="ledger-table">
          <thead>
            <tr>
              <th className="w-28">ID</th>
              <th>Claim</th>
              <th className="w-44">Source</th>
              <th className="w-24">Page</th>
              <th className="w-28">Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => {
              const evidence = claimEvidenceList(claim);
              const page = evidence.length ? evidencePage(evidence[0]) : undefined;
              return (
                <tr key={claim.id} onClick={() => onSelect(claim)} className="ledger-row">
                  <td><span className="ledger-id">{claim.id.slice(0, 8)}</span></td>
                  <td><div className="ledger-claim">{claimText(claim)}</div></td>
                  <td><div className="ledger-source">{claimDocumentName(claim, documents) || "—"}</div></td>
                  <td className="ledger-muted">{page !== undefined ? `p. ${page}` : "—"}</td>
                  <td>
                    {claim.verified ? (
                      <span className="status-chip status-verified"><Check size={12} /> Verified</span>
                    ) : (
                      <span className="status-chip status-pending"><Minus size={12} /> Unverified</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="ledger-footer">{claims.length} {claims.length === 1 ? "claim" : "claims"} · Select a row to inspect evidence</div>
    </div>
  );
}
