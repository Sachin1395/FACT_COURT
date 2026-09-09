"use client";

import { useRef, useState, type DragEvent } from "react";
import { UploadCloud, X, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/Button";

interface DocumentUploadProps {
  onUpload: (files: File[]) => Promise<void>;
}

export function DocumentUpload({ onUpload }: DocumentUploadProps) {
  const [staged, setStaged] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<"success" | "error" | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(fileList: FileList | File[]) {
    const pdfs = Array.from(fileList).filter(
      (f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf")
    );
    setStaged((prev) => [...prev, ...pdfs]);
    setResult(null);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files);
  }

  function removeFile(index: number) {
    setStaged((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleProcess() {
    if (staged.length === 0) return;
    setProcessing(true);
    setResult(null);
    try {
      await onUpload(staged);
      setStaged([]);
      setResult("success");
    } catch {
      setResult("error");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center text-center rounded-lg border border-dashed px-6 py-8 cursor-pointer transition-colors ${
          dragging
            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
            : "border-[var(--line-strong)] bg-[var(--paper-raised)] hover:border-[var(--ink-faint)]"
        }`}
      >
        <UploadCloud size={22} strokeWidth={1.5} className="text-[var(--ink-faint)] mb-2.5" />
        <p className="text-sm text-[var(--ink)] font-medium">Drop PDFs here or click to browse</p>
        <p className="text-xs text-[var(--ink-faint)] mt-1">PDF files only</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {staged.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1.5">
          {staged.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between text-sm border border-[var(--line)] rounded-md px-3 py-2 bg-[var(--paper-raised)]"
            >
              <span className="truncate text-[var(--ink)]">{file.name}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeFile(i);
                }}
                aria-label={`Remove ${file.name}`}
                className="text-[var(--ink-faint)] hover:text-[var(--danger)] shrink-0 ml-2 cursor-pointer"
              >
                <X size={14} strokeWidth={2} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-center gap-3">
        <Button
          variant="primary"
          size="sm"
          disabled={staged.length === 0 || processing}
          onClick={handleProcess}
        >
          {processing && <Loader2 size={14} className="animate-spin" strokeWidth={2} />}
          {processing ? "Processing…" : "Process Documents"}
        </Button>
        {result === "error" && (
          <span className="text-xs text-[var(--danger)]">
            Upload failed. Check the files and try again.
          </span>
        )}
        {result === "success" && (
          <span className="text-xs text-[var(--accent)] flex items-center gap-1">
            <CheckCircle2 size={13} strokeWidth={2} />
            Documents processed
          </span>
        )}
      </div>

      {processing && (
        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--ink-soft)] border border-[var(--line)] bg-[var(--accent-soft)]/40 rounded-md px-3 py-2">
          <Loader2 size={13} className="animate-spin text-[var(--accent)]" strokeWidth={2} />
          <span>
            <span className="font-medium text-[var(--ink)]">Processing documents…</span>{" "}
            Extracting facts and comparing evidence.
          </span>
        </div>
      )}
    </div>
  );
}
