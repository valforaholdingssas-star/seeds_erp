import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variants = {
  info: "border-green-900/15 bg-green-900/5 text-green-900",
  caution: "border-terracotta-600/25 bg-terracotta-600/8 text-terracotta-600",
  success: "border-sage-500/30 bg-sage-500/10 text-green-900",
  error: "border-wine-900/25 bg-wine-900/8 text-wine-900",
} as const;

export function Alert({
  variant = "info",
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { variant?: keyof typeof variants }) {
  return (
    <div
      className={cn(
        "rounded-[24px] border px-4 py-3 text-sm leading-relaxed",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
