import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Option = { value: string; label: string };

type Props = {
  value: string;
  options: Option[];
  display?: string;
  tone?: "dark" | "sage" | "terracotta" | "wine";
  disabled?: boolean;
  onChange: (value: string) => void | Promise<void>;
  /** Wider dropdown for long labels (e.g. EFE accounts). */
  selectClassName?: string;
  buttonClassName?: string;
};

const toneClass: Record<NonNullable<Props["tone"]>, string> = {
  dark: "bg-green-900 text-text-on-dark",
  sage: "bg-sage-500/20 text-green-900",
  terracotta: "bg-terracotta-600/15 text-terracotta-600",
  wine: "bg-wine-900/15 text-wine-900",
};

export function InlineSelect({
  value,
  options,
  display,
  tone = "dark",
  disabled,
  onChange,
  selectClassName,
  buttonClassName,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLSelectElement>(null);

  useEffect(() => {
    if (editing) ref.current?.focus();
  }, [editing]);

  const label =
    display || options.find((o) => o.value === value)?.label || value || "—";

  if (disabled) {
    return (
      <span className={cn("inline-flex rounded-full px-2.5 py-1 text-[10px] label-caps", toneClass[tone])}>
        {label}
      </span>
    );
  }

  if (editing) {
    return (
      <select
        ref={ref}
        className={cn(
          "max-w-[min(100vw,22rem)] rounded-full border border-line bg-warm-white px-2 py-1 text-xs outline-none focus:ring-2 focus:ring-sage-500/30",
          selectClassName,
        )}
        value={value}
        disabled={saving}
        onChange={async (e) => {
          const next = e.target.value;
          if (next === value) {
            setEditing(false);
            return;
          }
          setSaving(true);
          try {
            await onChange(next);
            setEditing(false);
          } finally {
            setSaving(false);
          }
        }}
        onBlur={() => {
          if (!saving) setEditing(false);
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {options.map((o) => (
          <option key={o.value || "__empty"} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <button
      type="button"
      title="Clic para cambiar"
      onClick={(e) => {
        e.stopPropagation();
        setEditing(true);
      }}
      className={cn(
        "inline-flex max-w-[min(100vw,22rem)] items-center gap-1 truncate rounded-full px-2.5 py-1 text-left text-[10px] label-caps transition-all hover:ring-2 hover:ring-sage-500/30",
        toneClass[tone],
        saving && "opacity-60",
        buttonClassName,
      )}
    >
      <span className="truncate">{label}</span>
      <span aria-hidden className="shrink-0 text-[8px] opacity-70">
        ▾
      </span>
    </button>
  );
}
