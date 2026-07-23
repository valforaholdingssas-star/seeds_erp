import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const fieldClass =
  "w-full rounded-[16px] border border-line bg-warm-white px-4 py-3 text-[15px] text-text-dark placeholder:text-text-soft outline-none transition-all duration-[160ms] ease-soft focus:border-green-900/35 focus:ring-2 focus:ring-sage-500/25";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(fieldClass, className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(fieldClass, "min-h-28 resize-y", className)} {...props} />
));
Textarea.displayName = "Textarea";

export function FieldLabel({
  children,
  htmlFor,
}: {
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="label-caps mb-2 block text-text-muted">
      {children}
    </label>
  );
}
