import Link from "next/link";
import type { Session } from "@/lib/types";
import { formatDate, shortId } from "@/lib/utils";

interface SessionListProps {
  sessions: Session[];
  variant?: "grid" | "rail";
  activeId?: string;
}

export function SessionList({ sessions, variant = "grid", activeId }: SessionListProps) {
  if (variant === "rail") {
    return (
      <nav className="flex flex-col gap-0.5">
        {sessions.map((session) => {
          const active = session.id === activeId;
          return (
            <Link
              key={session.id}
              href={`/sessions/${encodeURIComponent(session.id)}`}
              className={`rounded-md px-3 py-2.5 text-sm transition-colors border ${
                active
                  ? "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent-soft)] font-medium"
                  : "text-[var(--ink-soft)] border-transparent hover:bg-[var(--paper-raised)] hover:border-[var(--line)]"
              }`}
            >
              <div className="truncate">Session {shortId(session.id, 8)}</div>
              {formatDate(session.created_at) && (
                <div className="text-[11px] text-[var(--ink-faint)] mt-0.5">
                  {formatDate(session.created_at)}
                </div>
              )}
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {sessions.map((session) => (
        <Link
          key={session.id}
          href={`/sessions/${encodeURIComponent(session.id)}`}
          className="border border-[var(--line)] rounded-lg p-4 bg-[var(--paper-raised)] hover:border-[var(--ink)] transition-colors"
        >
          <div className="text-[11px] font-mono text-[var(--ink-faint)] mb-1.5">
            {shortId(session.id, 10)}
          </div>
          <div className="font-serif text-base text-[var(--ink)]">
            {(session.name as string) || "Analysis session"}
          </div>
          {formatDate(session.created_at) && (
            <div className="text-xs text-[var(--ink-faint)] mt-2">
              Created {formatDate(session.created_at)}
            </div>
          )}
        </Link>
      ))}
    </div>
  );
}
