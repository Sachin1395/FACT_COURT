"use client";

import {
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  Trash2,
} from "lucide-react";
import type { DocumentItem } from "@/lib/types";

type DocumentListProps = {
  documents: DocumentItem[] | null;
  onDelete: (documentId: string) => void;
};

function getStatus(document: DocumentItem) {
  const value = String(document.status ?? "").toLowerCase().trim();

  if (
    value.includes("fail") ||
    value.includes("error")
  ) {
    return "failed";
  }

  // Check completed states BEFORE processing states.
  if (
    value.includes("complete") ||
    value.includes("completed") ||
    value.includes("done") ||
    value.includes("success") ||
    value.includes("successful") ||
    value.includes("ready") ||
    value === "processed" ||
    value === "finished"
  ) {
    return "complete";
  }

  if (
    value.includes("processing") ||
    value.includes("extracting") ||
    value.includes("pending") ||
    value.includes("queued") ||
    value.includes("queue") ||
    value.includes("uploading") ||
    value === "parsed"
  ) {
    return "processing";
  }

  return "complete";
}

function Status({ document }: { document: DocumentItem }) {
  const status = getStatus(document);

  if (status === "processing") {
    return (
      <div className="flex items-center gap-1.5 text-xs text-[var(--ink-soft)]">
        <Loader2
          size={13}
          strokeWidth={1.8}
          className="animate-spin"
        />
        <span>Processing</span>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex items-center gap-1.5 text-xs text-red-600">
        <XCircle size={13} strokeWidth={1.8} />
        <span>Failed</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-emerald-700">
      <CheckCircle2 size={13} strokeWidth={1.8} />
      <span>Complete</span>
    </div>
  );
}

export function DocumentList({
  documents,
  onDelete,
}: DocumentListProps) {
  if (!documents) {
    return (
      <div className="border border-[var(--line)] rounded-lg p-6 text-sm text-[var(--ink-faint)]">
        Loading documents…
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="border border-[var(--line)] rounded-lg p-8 text-center">
        <FileText
          size={22}
          className="mx-auto text-[var(--ink-faint)]"
          strokeWidth={1.5}
        />

        <p className="mt-3 text-sm text-[var(--ink-soft)]">
          No documents uploaded yet.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--line)] rounded-lg overflow-hidden">
      <div className="divide-y divide-[var(--line)]">
        {documents.map((document) => (
          <div
            key={document.id}
            className="flex items-center justify-between gap-4 px-4 py-3"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="shrink-0">
                <FileText
                  size={17}
                  strokeWidth={1.6}
                  className="text-[var(--ink-faint)]"
                />
              </div>

              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-[var(--ink)]">
                  {document.filename || "Untitled document"}
                </p>

                <div className="mt-1">
                  <Status document={document} />
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => onDelete(document.id)}
              className="shrink-0 rounded-md p-1.5 text-[var(--ink-faint)] hover:bg-[var(--paper-raised)] hover:text-red-600"
              title="Delete document"
            >
              <Trash2 size={15} strokeWidth={1.7} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}