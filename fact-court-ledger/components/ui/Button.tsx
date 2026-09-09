import { type ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--accent)] disabled:hover:bg-[var(--ink)]",
  secondary:
    "bg-transparent text-[var(--ink)] border border-[var(--line-strong)] hover:border-[var(--ink)]",
  ghost:
    "bg-transparent text-[var(--ink-soft)] hover:text-[var(--ink)] hover:bg-[var(--accent-soft)]",
  danger:
    "bg-transparent text-[var(--danger)] border border-[var(--contradict-bg)] hover:bg-[var(--contradict-bg)]",
};

const sizeClasses: Record<Size, string> = {
  sm: "text-[13px] px-2.5 py-1.5 gap-1.5",
  md: "text-sm px-3.5 py-2 gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "secondary", size = "md", className = "", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={`inline-flex items-center justify-center rounded-md font-medium transition-colors duration-100 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
