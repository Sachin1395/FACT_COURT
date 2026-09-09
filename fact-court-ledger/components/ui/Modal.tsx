"use client";

import { useEffect, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer: ReactNode;
}

export function Modal({ open, onClose, title, children, footer }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-[var(--ink)]/30 animate-fade-in cursor-default"
      />
      <div className="relative w-full max-w-sm bg-[var(--paper-raised)] rounded-lg border border-[var(--line)] shadow-xl p-5 animate-fade-in">
        <h2 className="font-serif text-lg text-[var(--ink)] mb-2">{title}</h2>
        <div className="text-sm text-[var(--ink-soft)] leading-relaxed mb-5">
          {children}
        </div>
        <div className="flex justify-end gap-2">{footer}</div>
      </div>
    </div>
  );
}
