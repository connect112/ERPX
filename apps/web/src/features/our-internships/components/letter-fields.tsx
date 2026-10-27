import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { moveBy, removeAt, replaceAt } from "@/features/our-internships/lib/letters";

export const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

export function Field({ id, label, hint, children, className }: { id: string; label: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`space-y-1.5 ${className ?? ""}`}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function TextField({ id, label, value, onChange, hint, placeholder, maxLength, className }: { id: string; label: string; value: string; onChange: (v: string) => void; hint?: string; placeholder?: string; maxLength?: number; className?: string }) {
  return (
    <Field id={id} label={label} hint={hint} className={className}>
      <Input id={id} value={value} placeholder={placeholder} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

export function AreaField({ id, label, value, onChange, hint, rows = 3, maxLength }: { id: string; label: string; value: string; onChange: (v: string) => void; hint?: string; rows?: number; maxLength?: number }) {
  return (
    <Field id={id} label={label} hint={hint}>
      <Textarea id={id} rows={rows} value={value} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

export function NumberField({ id, label, value, onChange, min, max, step = 1, hint }: { id: string; label: string; value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; hint?: string }) {
  return (
    <Field id={id} label={label} hint={hint}>
      <Input
        id={id}
        type="number"
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const n = parseFloat(e.target.value);
          if (Number.isFinite(n)) onChange(n);
        }}
      />
    </Field>
  );
}

export function SelectField<T extends string>({ id, label, value, onChange, options, hint }: { id: string; label: string; value: T; onChange: (v: T) => void; options: readonly { value: T; label: string }[]; hint?: string }) {
  return (
    <Field id={id} label={label} hint={hint}>
      <select id={id} className={selectClass} value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function CheckField({ id, label, checked, onChange, hint }: { id: string; label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium">
        <input id={id} type="checkbox" className="h-4 w-4" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        {label}
      </label>
      {hint && <p className="pl-6 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function ColorField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <Field id={id} label={label}>
      <div className="flex items-center gap-2">
        <input id={id} type="color" className="h-10 w-14 cursor-pointer rounded-md border bg-background p-1" value={value} onChange={(e) => onChange(e.target.value)} />
        <span className="text-sm tabular-nums text-muted-foreground">{value}</span>
      </div>
    </Field>
  );
}

/** A list of lines of text the admin can add to, edit, reorder and remove (documents, terms, notes). */
export function ListEditor({ id, label, items, onChange, addLabel, hint, rows = 2, max = 30 }: { id: string; label: string; items: string[]; onChange: (items: string[]) => void; addLabel: string; hint?: string; rows?: number; max?: number }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={`${id}-0`}>{label}</Label>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {items.length === 0 && <p className="text-sm text-muted-foreground">None. This section is left out of the letter.</p>}
      {items.map((item, i) => (
        <div key={i} className="flex items-start gap-2">
          <Textarea id={`${id}-${i}`} rows={rows} value={item} aria-label={`${label} ${i + 1}`} onChange={(e) => onChange(replaceAt(items, i, e.target.value))} />
          <div className="flex flex-col">
            <Button type="button" size="icon" variant="ghost" aria-label={`Move ${label} ${i + 1} up`} disabled={i === 0} onClick={() => onChange(moveBy(items, i, -1))}>
              <ArrowUp className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="icon" variant="ghost" aria-label={`Move ${label} ${i + 1} down`} disabled={i === items.length - 1} onClick={() => onChange(moveBy(items, i, 1))}>
              <ArrowDown className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="icon" variant="ghost" aria-label={`Remove ${label} ${i + 1}`} onClick={() => onChange(removeAt(items, i))}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" disabled={items.length >= max} onClick={() => onChange([...items, ""])}>
        <Plus className="h-3.5 w-3.5" />
        {addLabel}
      </Button>
    </div>
  );
}
