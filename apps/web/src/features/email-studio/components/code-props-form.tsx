import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CodeTemplate } from "@/features/email-studio/api/studio-api";

/**
 * The settings an approved React Email template declares. Administrators change these (never the code); a property left empty
 * uses the template's own default, and the colour properties follow the chosen brand until they are set here.
 */
export function CodePropsForm({ template, values, onChange }: { template: CodeTemplate; values: Record<string, string>; onChange: (next: Record<string, string>) => void }) {
  const set = (name: string, value: string) => onChange({ ...values, [name]: value });
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {template.description} This is an approved template: you change its settings below, and a developer changes its design.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {template.props.map((p) => {
          const id = `prop-${p.name}`;
          const value = values[p.name] ?? "";
          return (
            <div key={p.name} className={`space-y-1.5 ${p.type === "textarea" ? "sm:col-span-2" : ""}`}>
              <Label htmlFor={id}>
                {p.label}
                {p.required && <span aria-hidden="true"> *</span>}
              </Label>
              {p.type === "textarea" ? (
                <Textarea id={id} rows={3} value={value} placeholder={p.default} onChange={(e) => set(p.name, e.target.value)} />
              ) : p.type === "color" ? (
                <div className="flex items-center gap-2">
                  <input id={id} type="color" className="h-10 w-14 cursor-pointer rounded-md border bg-background p-1" value={value || p.default} onChange={(e) => set(p.name, e.target.value)} />
                  <span className="text-sm tabular-nums text-muted-foreground">{value || p.default}</span>
                  {value && (
                    <button type="button" className="text-xs underline" onClick={() => set(p.name, "")}>
                      Use the brand's
                    </button>
                  )}
                </div>
              ) : (
                <Input id={id} value={value} placeholder={p.default} onChange={(e) => set(p.name, e.target.value)} />
              )}
              {p.description && <p className="text-xs text-muted-foreground">{p.description}</p>}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Placeholders such as {"{{full_name}}"} work in any text setting. The email also uses: {template.placeholders.map((n) => `{{${n}}}`).join(", ")}.
      </p>
    </div>
  );
}
