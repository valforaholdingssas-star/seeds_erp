import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 label-caps min-h-11 px-6 rounded-[999px] transition-all duration-[160ms] ease-soft disabled:opacity-45 disabled:pointer-events-none hover:-translate-y-px active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sage-500/40",
  {
    variants: {
      variant: {
        "primary-dark": "bg-green-900 text-text-on-dark hover:bg-green-950",
        "primary-wine": "bg-wine-900 text-text-on-dark hover:bg-[#4a0503]",
        cream: "bg-cream-100 text-green-900 border border-line hover:bg-warm-white",
        outline: "bg-transparent text-green-900 border border-line hover:bg-green-900/5",
        ghost: "bg-transparent text-green-900 hover:bg-green-900/5",
      },
      size: {
        default: "min-h-11 px-6 text-[11px]",
        sm: "min-h-9 px-4 text-[10px]",
        lg: "min-h-12 px-8 text-[12px]",
      },
    },
    defaultVariants: {
      variant: "primary-dark",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
