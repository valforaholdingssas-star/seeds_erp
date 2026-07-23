import { forwardRef, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const fieldClass =
  "w-full rounded-[16px] border border-line bg-warm-white px-4 py-3 text-[15px] text-text-dark outline-none transition-all duration-[160ms] ease-soft focus:border-green-900/35 focus:ring-2 focus:ring-sage-500/25 appearance-none";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <div className="relative">
      <select ref={ref} className={cn(fieldClass, "pr-10", className)} {...props}>
        {children}
      </select>
      <span
        aria-hidden
        className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-text-soft"
      >
        ▾
      </span>
    </div>
  ),
);
Select.displayName = "Select";
