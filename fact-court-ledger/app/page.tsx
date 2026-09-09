"use client";

import { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/layout/Header";
import { SessionList } from "@/components/sessions/SessionList";
import { SessionEmptyState } from "@/components/sessions/SessionEmptyState";
import { NewSessionButton } from "@/components/sessions/NewSessionButton";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { listSessions } from "@/lib/api";
import type { Session } from "@/lib/types";

export default function HomePage() {
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch {
      setError("Unable to load sessions.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        right={sessions && sessions.length > 0 ? <NewSessionButton /> : undefined}
      />
      <main className="flex-1 max-w-5xl w-full mx-auto px-5 sm:px-8 py-10">
        <div className="mb-8">
          <h1 className="font-serif text-2xl text-[var(--ink)] mb-1.5">
            Analysis sessions
          </h1>
          <p className="text-sm text-[var(--ink-soft)]">
            Each session is an isolated workspace of documents, extracted claims, and the
            relationships found between them.
          </p>
        </div>

        {error && <ErrorState message={error} onRetry={load} />}

        {!error && sessions === null && <LoadingSkeleton variant="card" count={3} />}

        {!error && sessions !== null && sessions.length === 0 && <SessionEmptyState />}

        {!error && sessions !== null && sessions.length > 0 && (
          <SessionList sessions={sessions} variant="grid" />
        )}
      </main>
    </div>
  );
}
