import { Search } from "lucide-react";
import { typeLabel } from "./TypeBadge";

interface RelationshipFiltersProps {
  search: string;
  onSearchChange: (v: string) => void;
  activeType: string;
  onTypeChange: (v: string) => void;
  availableTypes: string[];
}

export function RelationshipFilters({
  search,
  onSearchChange,
  activeType,
  onTypeChange,
  availableTypes,
}: RelationshipFiltersProps) {
  const types = ["all", "corroborates", "contradicts", "reconciles"];
  // Include any additional types the backend returned that we don't know about yet.
  for (const t of availableTypes) {
    if (!types.includes(t)) types.push(t);
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="relative flex-1 max-w-xs">
        <Search
          size={14}
          strokeWidth={1.75}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)]"
        />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search facts…"
          className="w-full text-sm border border-[var(--line-strong)] rounded-md bg-[var(--paper-raised)] pl-8 pr-3 py-1.5 text-[var(--ink)] placeholder:text-[var(--ink-faint)]"
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {types.map((type) => {
          const active = type === activeType;
          return (
            <button
              key={type}
              onClick={() => onTypeChange(type)}
              className={`text-xs font-medium px-2.5 py-1.5 rounded-full border transition-colors cursor-pointer ${
                active
                  ? "bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)]"
                  : "text-[var(--ink-soft)] border-[var(--line-strong)] hover:border-[var(--ink)]"
              }`}
            >
              {type === "all" ? "All" : typeLabel(type)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
