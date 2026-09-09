"use client";

import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Drawer({ open, onClose, title, children }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-[var(--ink)]/30 animate-fade-in cursor-default"
      />
      <div className="relative w-full sm:max-w-xl h-full bg-[var(--paper-raised)] shadow-xl flex flex-col animate-slide-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--line)] shrink-0">
          <h2 className="font-serif text-lg text-[var(--ink)]">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="p-1.5 rounded-md text-[var(--ink-soft)] hover:bg-[var(--accent-soft)] hover:text-[var(--ink)] transition-colors cursor-pointer"
          >
            <X size={18} strokeWidth={1.75} />
          </button>
        </div>
        <div className="overflow-y-auto thin-scroll flex-1 px-5 py-5">{children}</div>
      </div>
    </div>
  );
}
