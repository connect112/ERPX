import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type ComponentKind, type ComponentPayload, type EmailComponent, studioApi, studioKeys, useComponents } from "@/features/email-studio/api/studio-api";
import { useStudioPermissions } from "@/features/email-studio/lib/permissions";
import { errorMessage } from "@/features/institutions/lib/format";
import { SelectField, TextField } from "@/features/our-internships/components/letter-fields";

const KINDS: { value: ComponentKind; label: string }[] = [
  { value: "header", label: "Header" },
  { value: "footer", label: "Footer" },
  { value: "button", label: "Call-to-action button" },
  { value: "announcement", label: "Announcement section" },
  { value: "info_card", label: "Information card" },
  { value: "internship_details", label: "Internship details block" },
  { value: "warning", label: "Warning notice" },
  { value: "contact", label: "Contact section" },
];

const STARTER: Record<ComponentKind, string> = {
  header: '<table width="100%" role="presentation"><tr><td align="center" style="padding:16px;border-bottom:3px solid #2563eb"><strong style="font-size:20px">{{company_name}}</strong></td></tr></table>',
  footer: '<table width="100%" role="presentation"><tr><td align="center" style="padding:16px;font-size:12px;color:#6b7280">{{company_name}} · {{company_address}}</td></tr></table>',
  button: '<table role="presentation"><tr><td style="background-color:#2563eb;border-radius:6px"><a href="{{login_url}}" style="display:inline-block;padding:12px 24px;color:#ffffff;text-decoration:none;font-weight:600">Open</a></td></tr></table>',
  announcement: '<table width="100%" role="presentation"><tr><td style="padding:16px;background-color:#eff6ff;border-radius:6px"><strong>Announcement</strong><br />Write the news here.</td></tr></table>',
  info_card: '<table width="100%" role="presentation"><tr><td style="padding:16px;border:1px solid #e5e7eb;border-radius:6px">Write the details here.</td></tr></table>',
  internship_details:
    '<table width="100%" role="presentation"><tr><td style="padding:16px;border:1px solid #e5e7eb;border-radius:6px"><strong>{{internship_name}}</strong><br />Position: {{internship_position}}<br />{{internship_start_date}} to {{internship_end_date}}</td></tr></table>',
  warning: '<table width="100%" role="presentation"><tr><td style="padding:12px 16px;background-color:#fef3c7;color:#92400e;border-radius:6px">Please read this carefully.</td></tr></table>',
  contact: '<table width="100%" role="presentation"><tr><td style="padding:16px;font-size:13px">Questions? Write to {{company_email}} or call {{company_phone}}.</td></tr></table>',
};

/** Reusable blocks for emails. Copy one into an HTML email or a design; they are cleaned like any email HTML. */
export function ComponentsPage() {
  const list = useComponents();
  const perms = useStudioPermissions();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<EmailComponent | "new" | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const remove = useMutation({ mutationFn: (id: string) => studioApi.deleteComponent(id), onSuccess: () => queryClient.invalidateQueries({ queryKey: studioKeys.components }) });
  if (list.isLoading) return <Skeleton className="h-48 w-full" />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Headers, footers, buttons and notices you reuse. A brand's own header and footer are placed with {"{{brand_header}}"} and {"{{brand_footer}}"}; the blocks here are for you to copy into HTML emails.
        </p>
        <Button disabled={!perms.canManage} onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4" /> New component
        </Button>
      </div>
      {remove.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete it.")}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        {list.data?.map((c) => (
          <div key={c.id} className="space-y-2 rounded-lg border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">{c.name}</p>
              <Badge variant="outline">{KINDS.find((k) => k.value === c.kind)?.label ?? c.kind}</Badge>
            </div>
            {c.description && <p className="text-sm text-muted-foreground">{c.description}</p>}
            <iframe title={`${c.name} preview`} sandbox="" srcDoc={`<body style="margin:8px;font-family:Arial,sans-serif">${c.html}</body>`} className="h-32 w-full rounded border bg-white" />
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={!perms.canManage} onClick={() => setEditing(c)}>
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
              <Button size="sm" variant="ghost" onClick={async () => { await navigator.clipboard.writeText(c.html); setCopied(c.id); }}>
                <Copy className="h-3.5 w-3.5" /> {copied === c.id ? "Copied" : "Copy HTML"}
              </Button>
              <Button size="sm" variant="ghost" aria-label={`Delete ${c.name}`} disabled={!perms.canManage || remove.isPending} onClick={() => { if (window.confirm(`Delete "${c.name}"?`)) remove.mutate(c.id); }}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
        {list.data?.length === 0 && <p className="rounded-md border p-8 text-center text-sm text-muted-foreground md:col-span-2">No components yet.</p>}
      </div>
      {editing && <ComponentDialog component={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function ComponentDialog({ component, onClose }: { component: EmailComponent | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ComponentPayload>(component ?? { name: "", kind: "info_card", description: "", html: STARTER.info_card });
  const save = useMutation({
    mutationFn: () => studioApi.saveComponent(form, component?.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studioKeys.components });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{component ? `Edit ${component.name}` : "New component"}</DialogTitle>
          <DialogDescription>Email HTML with inline styles. Anything unsafe is removed when you save.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="cp-name" label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} maxLength={120} />
          <SelectField id="cp-kind" label="Kind" value={form.kind} options={KINDS} onChange={(v) => setForm({ ...form, kind: v, html: !component && form.html === STARTER[form.kind] ? STARTER[v] : form.html })} />
          <div className="sm:col-span-2">
            <TextField id="cp-desc" label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} maxLength={300} />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="cp-html" className="text-sm font-medium">HTML</label>
            <Textarea id="cp-html" rows={12} className="font-mono text-xs" value={form.html} onChange={(e) => setForm({ ...form, html: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <span className="text-sm font-medium">Preview</span>
            <iframe title="Component preview" sandbox="" srcDoc={`<body style="margin:8px;font-family:Arial,sans-serif">${form.html}</body>`} className="h-[17rem] w-full rounded border bg-white" />
          </div>
        </div>
        {save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error, "Could not save the component.")}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={!form.name.trim() || !form.html.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving..." : "Save component"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
