import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

const tones = {
  cream: "bg-cream-100 text-text-dark border-line",
  "warm-white": "bg-warm-white text-text-dark border-line",
  dark: "bg-green-900 text-text-on-dark border-line-dark",
} as const;

export function Card({
  tone = "warm-white",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  tone?: keyof typeof tones;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-[32px] border p-6 shadow-[var(--shadow-1)] transition-transform duration-[280ms] ease-soft",
        tones[tone],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
