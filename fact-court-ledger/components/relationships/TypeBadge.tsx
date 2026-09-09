import { Link2, SplitSquareHorizontal, Scale } from "lucide-react";

const KNOWN_TYPES: Record<
  string,
  { label: string; color: string; bg: string; icon: React.ComponentType<{ size?: number; strokeWidth?: number }> }
> = {
  corroborates: {
    label: "Corroborates",
    color: "var(--corroborate)",
    bg: "var(--corroborate-bg)",
    icon: Link2,
  },
  contradicts: {
    label: "Contradicts",
    color: "var(--contradict)",
    bg: "var(--contradict-bg)",
    icon: SplitSquareHorizontal,
  },
  reconciles: {
    label: "Reconciles",
    color: "var(--reconcile)",
    bg: "var(--reconcile-bg)",
    icon: Scale,
  },
};

export function typeLabel(type: string): string {
  const known = KNOWN_TYPES[type.toLowerCase()];
  if (known) return known.label;
  if (!type || type === "unknown") return "Unclassified";
  // Turn "some_new_type" into "Some new type" for unknown backend values.
  return type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, " ");
}

export function TypeBadge({ type, size = "md" }: { type: string; size?: "sm" | "md" }) {
  const known = KNOWN_TYPES[type.toLowerCase()];
  const Icon = known?.icon;
  const color = known?.color ?? "var(--neutral-badge)";
  const bg = known?.bg ?? "var(--neutral-badge-bg)";
  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium tracking-wide ${padding}`}
      style={{ color, backgroundColor: bg }}
    >
      {Icon && <Icon size={size === "sm" ? 11 : 12} strokeWidth={2.25} />}
      {typeLabel(type)}
    </span>
  );
}
