"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { Button } from "../ui/Button";
import { createSession } from "@/lib/api";

export function NewSessionButton({
  variant = "primary",
  label = "New Session",
}: {
  variant?: "primary" | "secondary";
  label?: string;
}) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const session = await createSession();
      router.push(`/sessions/${encodeURIComponent(session.id)}`);
    } catch {
      setError("Couldn't create a session. Try again.");
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button variant={variant} size="sm" onClick={handleCreate} disabled={creating}>
        {creating ? (
          <Loader2 size={14} className="animate-spin" strokeWidth={2} />
        ) : (
          <Plus size={14} strokeWidth={2} />
        )}
        {label}
      </Button>
      {error && <span className="text-xs text-[var(--danger)]">{error}</span>}
    </div>
  );
}
