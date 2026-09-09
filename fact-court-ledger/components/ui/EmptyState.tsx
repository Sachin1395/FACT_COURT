import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center text-center gap-2 py-12 px-6">
      {icon && <div className="text-[var(--ink-faint)] mb-1">{icon}</div>}
      <p className="font-serif text-lg text-[var(--ink)]">{title}</p>
      {description && (
        <p className="text-sm text-[var(--ink-soft)] max-w-sm leading-relaxed">
          {description}
        </p>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
