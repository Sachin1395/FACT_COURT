import { AlertCircle } from "lucide-react";
import { Button } from "./Button";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center text-center gap-2 py-12 px-6">
      <AlertCircle size={20} className="text-[var(--danger)] mb-1" strokeWidth={1.75} />
      <p className="font-serif text-lg text-[var(--ink)]">{title}</p>
      <p className="text-sm text-[var(--ink-soft)] max-w-sm leading-relaxed">{message}</p>
      {onRetry && (
        <div className="mt-3">
          <Button size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
