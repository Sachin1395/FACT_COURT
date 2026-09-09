export type DashboardTab = "relationships" | "claims" | "documents";

const TABS: { id: DashboardTab; label: string }[] = [
  { id: "relationships", label: "Relations Ledger" },
  { id: "claims", label: "Claim Ledger" },
  { id: "documents", label: "Documents" },
];

export function DashboardTabs({
  active,
  onChange,
}: {
  active: DashboardTab;
  onChange: (tab: DashboardTab) => void;
}) {
  return (
    <div className="flex border-b border-[var(--line)] gap-1">
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`px-3.5 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors cursor-pointer ${
              isActive
                ? "border-[var(--ink)] text-[var(--ink)]"
                : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-soft)]"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
