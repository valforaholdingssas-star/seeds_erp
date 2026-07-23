import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variants = {
  sage: "bg-sage-500/15 text-green-900",
  terracotta: "bg-terracotta-600/12 text-terracotta-600",
  wine: "bg-wine-900/10 text-wine-900",
  dark: "bg-green-900 text-text-on-dark",
  rose: "bg-rose-300/25 text-green-900",
} as const;

export function Badge({
  variant = "sage",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: keyof typeof variants }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 label-caps",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
