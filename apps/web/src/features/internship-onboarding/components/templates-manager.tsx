import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/api/client";
import { errorMessage } from "@/features/institutions/lib/format";
import type { TemplateRow } from "@/features/internship-onboarding/api";
import { money } from "@/features/internship-onboarding/lib/format";

const T = "/internship-onboarding-templates";
const templatesApi = {
  all: () => apiClient.get<TemplateRow[]>(T, { params: { include_archived: true } }).then((r) => r.data),
  rename: (id: string, name: string) => apiClient.patch<TemplateRow>(`${T}/${id}`, { name }).then((r) => r.data),
  duplicate: (id: string, name: string) => apiClient.post<TemplateRow>(`${T}/${id}/duplicate`, { name }).then((r) => r.data),
  archive: (id: string, archived: boolean) => apiClient.post<TemplateRow>(`${T}/${id}/archive`, { archived }).then((r) => r.data),
};

/** Reusable onboarding setups: see what each holds, rename, duplicate, archive. Applying one is done from Settings. */
export function TemplatesManager() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["onboarding-templates", "all"], queryFn: templatesApi.all });
  const [names, setNames] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["onboarding-templates"] });
    },
    onError: (e) => setError(errorMessage(e, "That did not work.")),
  });

  return (
    <div className="space-y-2 text-sm">
      {error && <p className="text-destructive">{error}</p>}
      {(list.data ?? []).length === 0 && !list.isLoading && <p className="text-muted-foreground">No templates yet. Save an internship's settings as a template.</p>}
      {(list.data ?? []).map((t) => {
        const s = t.settings;
        return (
          <div key={t.id} className={`space-y-2 rounded-md border p-2 ${t.archived ? "opacity-60" : ""}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{t.name}</span>
              <Badge variant="outline">v{t.version}</Badge>
              {t.archived && <Badge variant="secondary">archived</Badge>}
              <span className="text-xs text-muted-foreground">updated {new Date(t.updated_at).toLocaleDateString()}</span>
              <Button size="sm" variant="ghost" onClick={() => setOpen(open === t.id ? null : t.id)}>
                {open === t.id ? "Hide" : "Preview"}
              </Button>
            </div>
            {open === t.id && (
              <ul className="list-disc pl-5 text-xs text-muted-foreground">
                <li>Mode: {s.modes.mode}; documents {s.modes.require_documents ? "verified" : "not required"}; payment {s.modes.require_payment ? `${money(s.fees.base_amount)} via ${s.fees.methods.join(", ") || "—"}` : "not required"}</li>
                <li>Documents: {s.documents.map((d) => d.label).join(", ") || "none"}</li>
                <li>Questions: {s.form.map((f) => f.label).join(", ") || "none"}</li>
                <li>Declaration terms v{s.declaration.terms_version}; reminders {s.communication.reminder_days.join("/")} days before closing</li>
                <li>Deadlines and fees are set per internship after applying.</li>
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              <Input className="max-w-[220px]" placeholder="New name" value={names[t.id] ?? ""} onChange={(e) => setNames({ ...names, [t.id]: e.target.value })} />
              <Button size="sm" variant="outline" disabled={!names[t.id]?.trim()} onClick={() => act.mutate(() => templatesApi.rename(t.id, names[t.id]))}>
                Rename
              </Button>
              <Button size="sm" variant="outline" disabled={!names[t.id]?.trim()} onClick={() => act.mutate(() => templatesApi.duplicate(t.id, names[t.id]))}>
                Duplicate as new name
              </Button>
              <Button size="sm" variant="ghost" onClick={() => act.mutate(() => templatesApi.archive(t.id, !t.archived))}>
                {t.archived ? "Restore" : "Archive"}
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
