import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Props = {
  value: string;
  placeholder?: string;
  title?: string;
  className?: string;
  multiline?: boolean;
  disabled?: boolean;
  onSave: (value: string) => void | Promise<void>;
};

export function InlineText({
  value,
  placeholder = "—",
  title = "Clic para editar",
  className,
  multiline,
  disabled,
  onSave,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (editing) {
      (multiline ? areaRef.current : inputRef.current)?.focus();
    }
  }, [editing, multiline]);

  async function commit() {
    const next = draft.trim();
    if (next === value.trim()) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(next);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (disabled) {
    return (
      <span className={cn("block truncate text-sm text-text-dark", className)}>
        {value || placeholder}
      </span>
    );
  }

  if (editing) {
    const common =
      "w-full min-w-[140px] rounded-[12px] border border-line bg-warm-white px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-sage-500/30";
    if (multiline) {
      return (
        <textarea
          ref={areaRef}
          rows={2}
          className={cn(common, "resize-none", className)}
          value={draft}
          disabled={saving}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => {
            if (!saving) void commit();
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void commit();
            }
          }}
          onClick={(e) => e.stopPropagation()}
        />
      );
    }
    return (
      <input
        ref={inputRef}
        className={cn(common, className)}
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (!saving) void commit();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void commit();
          }
          if (e.key === "Escape") {
            setDraft(value);
            setEditing(false);
          }
        }}
        onClick={(e) => e.stopPropagation()}
      />
    );
  }

  return (
    <button
      type="button"
      title={title}
      onClick={(e) => {
        e.stopPropagation();
        setEditing(true);
      }}
      className={cn(
        "block max-w-full truncate rounded-[8px] px-1 py-0.5 text-left text-sm text-text-dark transition-colors hover:bg-cream-100 hover:ring-1 hover:ring-sage-500/25",
        !value && "text-text-soft",
        saving && "opacity-60",
        className,
      )}
    >
      {value || placeholder}
    </button>
  );
}
