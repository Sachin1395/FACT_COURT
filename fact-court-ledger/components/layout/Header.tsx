import Link from "next/link";
import { Scale } from "lucide-react";
import type { ReactNode } from "react";

export function Header({ right }: { right?: ReactNode }) {
  return (
    <header className="flex items-center justify-between px-5 sm:px-8 py-4 border-b border-[var(--line)] bg-[var(--paper)] shrink-0">
      <Link href="/" className="flex items-center gap-2.5 group">
        <span className="flex items-center justify-center w-7 h-7 rounded-md bg-[var(--ink)] text-[var(--paper)] group-hover:bg-[var(--accent)] transition-colors">
          <Scale size={15} strokeWidth={1.75} />
        </span>
        <span>
          <span className="block font-serif text-[17px] leading-none text-[var(--ink)]">
            Fact Court
          </span>
          <span className="block text-[11px] leading-none text-[var(--ink-faint)] mt-1">
            Cross-document fact analysis
          </span>
        </span>
      </Link>
      {right}
    </header>
  );
}
