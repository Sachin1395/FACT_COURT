import type { Stats as StatsType } from "@/lib/types";
import { statValue } from "@/lib/utils";
import { LoadingSkeleton } from "../ui/LoadingSkeleton";

interface StatsProps {
  stats: StatsType | null;
  loading?: boolean;
}

export function Stats({ stats, loading }: StatsProps) {
  if (loading || !stats) {
    return (
      <div className="flex gap-3">
        <LoadingSkeleton variant="stat" count={3} />
      </div>
    );
  }

  const items = [
    { label: "Documents", value: statValue(stats, ["documents", "document_count"]) },
    { label: "Claims", value: statValue(stats, ["claims", "claim_count"]) },
    {
      label: "Relationships",
      value: statValue(stats, ["relationships", "relationship_count"]),
    },
  ];

  return (
    <div className="grid grid-cols-3 border border-[var(--line)] rounded-lg bg-[var(--paper-raised)] divide-x divide-[var(--line)]">
      {items.map((item) => (
        <div key={item.label} className="px-4 py-3.5">
          <div className="font-serif text-2xl text-[var(--ink)] leading-none">
            {item.value}
          </div>
          <div className="text-xs text-[var(--ink-soft)] mt-1.5">{item.label}</div>
        </div>
      ))}
    </div>
  );
}
