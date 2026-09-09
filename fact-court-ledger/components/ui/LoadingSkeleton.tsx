interface LoadingSkeletonProps {
  variant?: "row" | "card" | "stat";
  count?: number;
}

function Shimmer({ className = "" }: { className?: string }) {
  return (
    <div
      className={`bg-[var(--line)] rounded ${className}`}
      style={{
        background:
          "linear-gradient(90deg, var(--line) 0%, #ece9e1 50%, var(--line) 100%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s ease-in-out infinite",
      }}
    />
  );
}

export function LoadingSkeleton({ variant = "row", count = 3 }: LoadingSkeletonProps) {
  return (
    <div className="flex flex-col gap-2.5" aria-hidden="true">
      <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
      {Array.from({ length: count }).map((_, i) => {
        if (variant === "stat") {
          return <Shimmer key={i} className="h-14 flex-1" />;
        }
        if (variant === "card") {
          return (
            <div key={i} className="border border-[var(--line)] rounded-lg p-4 flex flex-col gap-2.5">
              <Shimmer className="h-3 w-24" />
              <Shimmer className="h-4 w-4/5" />
              <Shimmer className="h-3 w-2/5" />
            </div>
          );
        }
        return <Shimmer key={i} className="h-12 w-full" />;
      })}
    </div>
  );
}
