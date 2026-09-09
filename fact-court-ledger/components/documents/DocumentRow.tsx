"use client";

import { useState } from "react";
import { FileText, Trash2, Loader2 } from "lucide-react";
import type { DocumentItem } from "@/lib/types";
import { documentFilename, documentClaimCount, documentStatus } from "@/lib/utils";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";

interface DocumentRowProps {
  document: DocumentItem;
  onDelete: (id: string) => Promise<void>;
}

export function DocumentRow({ document, onDelete }: DocumentRowProps) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const claimCount = documentClaimCount(document);
  const status = documentStatus(document);

  async function handleDelete() {
    setDeleting(true);
    try {
      await onDelete(document.id);
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between gap-3 border border-[var(--line)] rounded-md px-3.5 py-2.5 bg-[var(--paper-raised)]">
        <div className="flex items-center gap-2.5 min-w-0">
          <FileText size={16} strokeWidth={1.5} className="text-[var(--ink-faint)] shrink-0" />
          <div className="min-w-0">
            <div className="text-sm text-[var(--ink)] truncate">{documentFilename(document)}</div>
            <div className="text-xs text-[var(--ink-faint)] mt-0.5">
              {typeof claimCount === "number" ? `${claimCount} claims` : status ?? ""}
            </div>
          </div>
        </div>
        <button
          onClick={() => setConfirming(true)}
          aria-label={`Delete ${documentFilename(document)}`}
          className="shrink-0 p-1.5 rounded-md text-[var(--ink-faint)] hover:text-[var(--danger)] hover:bg-[var(--contradict-bg)] transition-colors cursor-pointer"
        >
          <Trash2 size={15} strokeWidth={1.75} />
        </button>
      </div>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete this document?"
        footer={
          <>
            <Button size="sm" variant="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="danger" onClick={handleDelete} disabled={deleting}>
              {deleting && <Loader2 size={13} className="animate-spin" strokeWidth={2} />}
              Delete
            </Button>
          </>
        }
      >
        This will also remove claims and relationships derived from it.
      </Modal>
    </>
  );
}
