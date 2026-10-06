import { Code2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { insertCodeBlock, insertInlineCode } from "@/features/workshop-exams/lib/code-insert";
import { CODE_LANGUAGES } from "@/features/workshop-exams/lib/highlight";

// Remembered across fields so marking a run of Dockerfile questions is one pick.
let lastLanguage = "bash";

/**
 * A text box with a small "code" toolbar. Select the lines that are code and
 * press "Code block" to wrap them in ```language fences (nothing selected
 * inserts an empty block to type into); "Inline" wraps a selected word or
 * command in `backticks`. The result is plain text, so it also works when
 * pasted straight into "Paste many".
 */
export function CodeTextarea({
  value,
  onChange,
  rows,
  placeholder,
  ariaLabel,
  className = "",
  compact = false,
}: {
  value: string;
  onChange: (value: string) => void;
  rows: number;
  placeholder?: string;
  ariaLabel: string;
  className?: string;
  /** Show the toolbar only while this box has focus (used for the option boxes). */
  compact?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [language, setLanguage] = useState(lastLanguage);

  const apply = (edit: (value: string, start: number, end: number) => ReturnType<typeof insertCodeBlock>) => {
    const box = ref.current;
    if (!box) return;
    const result = edit(value, box.selectionStart, box.selectionEnd);
    onChange(result.value);
    // The value is applied on the next render; put the caret back afterwards.
    requestAnimationFrame(() => {
      box.focus();
      box.setSelectionRange(result.selectionStart, result.selectionEnd);
    });
  };

  return (
    <div className="group min-w-0 flex-1 space-y-1">
      <Textarea
        ref={ref}
        rows={rows}
        className={className}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
      />
      <div
        className={`flex-wrap items-center gap-2 text-xs text-muted-foreground ${
          compact ? "hidden group-focus-within:flex" : "flex"
        }`}
      >
        <Code2 className="h-3.5 w-3.5" aria-hidden />
        <select
          className="rounded-md border bg-background px-1.5 py-1 text-xs text-foreground"
          value={language}
          aria-label={`Code language for ${ariaLabel}`}
          onChange={(e) => {
            lastLanguage = e.target.value;
            setLanguage(e.target.value);
          }}
        >
          {CODE_LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          onClick={() => apply((v, s, e) => insertCodeBlock(v, s, e, language))}
        >
          Code block
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 px-2 text-xs"
          onClick={() => apply((v, s, e) => insertInlineCode(v, s, e))}
        >
          Inline code
        </Button>
        {!compact && <span>Select the code lines first to wrap them.</span>}
      </div>
    </div>
  );
}
